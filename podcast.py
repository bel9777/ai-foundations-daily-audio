"""AI Foundations podcast - two-host episode pipeline (Claude-side).

Replaces the ChatGPT-side single-voice narration loop. For every course day
(canon-adjudicated by the ai-foundations-kindle repo - HARD dependency,
fails loudly): generate a two-host dialogue script (Gemini text model),
render it with Gemini multi-speaker TTS (Alex=Puck, Jordan=Sulafat),
encode mp3, and publish.

TWO-WRITER SAFETY (until Brian retires the ChatGPT-side job):
- This pipeline writes ONLY parallel paths the old loop doesn't own:
  docs/audio-v2/, docs/transcripts-v2/, data/two-host-episodes.json.
- docs/feed.xml / feed.rss / index.html are NOT touched until every course
  day has a two-host episode. That completion flips the feed in one commit
  = the cutover moment; Brian must switch the ChatGPT job off then.
- An episode counts as done only if its mp3 exists on disk, so if the old
  loop's site build ever cleans unknown files, the next run regenerates.

Idempotent: done days are skipped; TTS free-tier quota (429) just pauses
the backfill and the next run continues.

Usage:
    py podcast.py            # status only
    py podcast.py --run      # generate missing, publish, push
    py podcast.py --run --limit 5
"""

import base64
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(HOME / "ai-foundations-kindle"))
try:
    from build import (gmail_token, pull_copies, select_days,  # noqa: E402
                       load_recovered)
except ImportError as e:  # hard dependency - never fail soft (f4 lesson)
    sys.exit(f"FATAL: cannot import ai-foundations-kindle build.py: {e}")

KEY = (HOME / ".ai-keys" / "gemini-api-key.txt").read_text().strip()
GBASE = "https://generativelanguage.googleapis.com/v1beta"
TEXT_MODEL = "gemini-flash-latest"
# Quota is PER MODEL. When the primary hits 429 the fallback still has a
# full bucket, which roughly doubles free-tier throughput instead of
# stalling the backfill until tomorrow. Same voices, same script; the
# plausibility gate polices quality either way.
# ORDER (2026-08-08 loudness audit): 2.5-flash is PRIMARY - every one of
# its renders measured stable (LRA 3.8-6.5), while most long
# 3.1-preview renders wobbled (LRA up to 23.6 - the "audio goes in and
# out" Brian reported on Day 1).
TTS_MODELS = ["gemini-2.5-flash-preview-tts", "gemini-3.1-flash-tts-preview"]
# every render is normalized to podcast loudness at encode time
AUDIO_FILTERS = "dynaudnorm=f=300:g=31:p=0.95,loudnorm=I=-16:TP=-1.5:LRA=7"
MAX_LRA, MIN_I, MAX_I = 8.5, -19.5, -13.5
CHUNK_PARTS = 4  # last-resort chunked render when a whole script 429s
FFMPEG = (HOME / r"AppData\Local\Microsoft\WinGet\Packages"
               r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
               r"\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe")

# split timeouts: the text call is quick; the TTS call must synthesize ~6
# min of 24 kHz audio and return it base64-inlined in one non-streaming
# response. A shared 300s timed out 3 of 13 day-attempts on 2026-08-06.
TEXT_TIMEOUT, TTS_TIMEOUT = 120, 600
RUN_CAP_SECONDS = 3 * 3600  # a bad run must not grind all day
# a good episode is ~2.4-3.4 spoken words/sec with only natural pauses;
# Day 43 shipped 50% digital silence at 1.53 wps and the duration-only
# gate could not see it (duration is computed from PCM bytes, and silence
# is bytes too)
MAX_SILENCE_RATIO, MIN_WORDS_PER_SEC = 0.10, 2.0

HOST, EXPERT = "Alex", "Jordan"
VOICE_HOST, VOICE_EXPERT = "Puck", "Sulafat"
SITE = "https://bel9777.github.io/ai-foundations-daily-audio"
# Audio is served from jsDelivr (the git branch), NOT from Pages. The
# legacy feed has always done this, which is the only reason Brian's
# listening was untouched by the 2026-08-06 Pages outage - during which
# every audio-v2 file was 404 on Pages and 200 on the CDN. Safe for a
# daily show despite jsDelivr's 12h s-maxage because every episode gets a
# UNIQUE filename (the byte size is embedded), so a new episode's URL has
# never been cached and cannot be served stale.
CDN = "https://cdn.jsdelivr.net/gh/bel9777/ai-foundations-daily-audio@main/docs"
STATE = REPO / "data" / "two-host-episodes.json"
AUDIO_DIR = REPO / "docs" / "audio-v2"
TRANS_DIR = REPO / "docs" / "transcripts-v2"
RUN_LOG = REPO / "_RUN-LOG.md"


def gapi(path, payload, timeout=300, attempts=3):
    """POST to Gemini, retrying transient 5xx.

    2026-08-07: a single HTTP 503 at day 33 killed a whole run and left 8
    episodes unmade. Server errors are transient and must not end the
    backfill; 429 (quota) must still propagate so the caller can stop.
    """
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(
            f"{GBASE}/{path}", data=json.dumps(payload).encode(),
            headers={"x-goog-api-key": KEY, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (500, 502, 503, 504) and attempt < attempts:
                wait = 20 * attempt
                print(f"    HTTP {e.code} - retry {attempt}/{attempts - 1} "
                      f"in {wait}s")
                time.sleep(wait)
                continue
            raise


def dialogue_prompt(day, title, lesson):
    return f"""You write scripts for a two-host educational podcast called
"AI Foundations Daily". Turn today's lesson into a natural conversation.

Hosts:
- {HOST}: the curious co-host. Sharp, asks the questions a smart listener
  would ask, occasionally pushes back or summarizes in plain words.
- {EXPERT}: the expert. Explains clearly with everyday analogies, keeps it
  grounded, never lectures for long without {HOST} jumping in.

Rules:
- Open with {HOST} giving a one-sentence hook about why today's topic
  matters, then "This is AI Foundations, day {day}." Then dive in.
- Cover every concept in the lesson and the worked example.
- Then {EXPERT} quizzes {HOST} with the lesson's knowledge-check
  questions - {HOST} answers in their own words, {EXPERT} confirms or
  sharpens.
- Then {EXPERT} assigns the lesson's hands-on exercise as homework in one
  tight beat: exactly what to do and what to notice while doing it.
- Close with a one-line tease of tomorrow's topic if the lesson names one.
- Sound like two real people: contractions, short sentences, occasional
  quick banter. No corporate speak, no "delve", no "great question", no
  filler praise between hosts.
- Plain spoken text only: no headings, no bullet lists, no stage
  directions, nothing in brackets or asterisks.
- Target 900-1050 words total (about six minutes of audio).
- FORMAT: every line starts with "{HOST}:" or "{EXPERT}:" followed by the
  words they say. Nothing else.

Today's lesson (Day {day}: {title}):
{lesson}"""


def gen_script(day, title, lesson):
    resp = gapi(f"models/{TEXT_MODEL}:generateContent", {
        "contents": [{"parts": [{"text": dialogue_prompt(day, title, lesson)}]}],
        "generationConfig": {"temperature": 0.8}}, timeout=TEXT_TIMEOUT)
    script = resp["candidates"][0]["content"]["parts"][0]["text"].strip()
    script = re.sub(r"^```.*$", "", script, flags=re.M).strip()
    lines = [ln for ln in script.splitlines() if ln.strip()]
    good = [ln for ln in lines if re.match(rf"^({HOST}|{EXPERT}):", ln.strip())]
    if len(good) < len(lines) - 2 or len(script.split()) < 500:
        raise ValueError(f"script failed QA: {len(good)}/{len(lines)} dialogue "
                         f"lines, {len(script.split())} words")
    return "\n".join(good)


def gen_audio(script):
    """Render the dialogue, falling through TTS_MODELS on quota errors.

    Returns (pcm, rate, model). Raises the LAST 429 only if every model
    is exhausted, so the caller's quota-stop logic still works.
    """
    last_429 = None
    for model in TTS_MODELS:
        try:
            return (*_gen_audio_with(script, model), model)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            last_429 = e
            print(f"    {model}: quota exhausted, trying next model")

    # LAST RESORT: render in chunks. The remaining free-tier allowance is
    # TOKEN-based, so several small requests can succeed where one large
    # one 429s (verified: a 2-line probe returned audio minutes after a
    # full ~1000-word script was refused). Raw PCM concatenates cleanly -
    # same rate, mono, 16-bit - and each chunk carries the same voice
    # config, so the speakers stay consistent across seams.
    for model in TTS_MODELS:
        try:
            parts, rate = [], None
            chunks = _split_script(script, CHUNK_PARTS)
            for i, chunk in enumerate(chunks, 1):
                pcm, rate = _gen_audio_with(chunk, model)
                parts.append(pcm)
                print(f"    {model}: chunk {i}/{len(chunks)} rendered")
                time.sleep(8)
            return b"".join(parts), rate, f"{model}+chunked"
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            last_429 = e
            print(f"    {model}: chunked render also quota-blocked")
    raise last_429


def _split_script(script, parts):
    """Split on speaker-line boundaries so no utterance is cut in half."""
    lines = [ln for ln in script.splitlines() if ln.strip()]
    size = -(-len(lines) // parts)  # ceil
    return ["\n".join(lines[i:i + size]) for i in range(0, len(lines), size)]


def _gen_audio_with(script, TTS_MODEL):
    resp = gapi(f"models/{TTS_MODEL}:generateContent", {
        "contents": [{"parts": [{"text":
            f"TTS the following podcast conversation between {HOST} and "
            f"{EXPERT}. {HOST} sounds curious and engaged; {EXPERT} sounds "
            "warm and clear. Natural conversational pacing.\n\n" + script}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"multiSpeakerVoiceConfig": {"speakerVoiceConfigs": [
                {"speaker": HOST, "voiceConfig":
                    {"prebuiltVoiceConfig": {"voiceName": VOICE_HOST}}},
                {"speaker": EXPERT, "voiceConfig":
                    {"prebuiltVoiceConfig": {"voiceName": VOICE_EXPERT}}}]}}}},
        timeout=TTS_TIMEOUT)
    part = resp["candidates"][0]["content"]["parts"][0]
    mime = part["inlineData"]["mimeType"]
    pcm = base64.b64decode(part["inlineData"]["data"])
    rate = int(re.search(r"rate=(\d+)", mime).group(1)) if "rate=" in mime else 24000
    return pcm, rate


def encode_mp3(pcm, rate, out_path):
    tmp = out_path.with_suffix(".tmp.wav")
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-i", str(tmp),
                    "-af", AUDIO_FILTERS,
                    "-codec:a", "libmp3lame", "-b:a", "96k", str(out_path)],
                   check=True)
    tmp.unlink()
    return len(pcm) / (rate * 2)


def loudness(path):
    """EBU R128: (integrated LUFS, loudness range LU)."""
    r = subprocess.run([str(FFMPEG), "-i", str(path), "-af", "ebur128",
                        "-f", "null", "-"], capture_output=True, text=True)
    tail = r.stderr[-2000:]
    return (float(re.search(r"I:\s*(-?[\d.]+) LUFS", tail).group(1)),
            float(re.search(r"LRA:\s*([\d.]+) LU", tail).group(1)))


def silence_ratio(path):
    """Fraction of the rendered file that is TRUE digital silence."""
    r = subprocess.run(
        [str(FFMPEG), "-i", str(path), "-af",
         "silencedetect=noise=-50dB:d=2", "-f", "null", "-"],
        capture_output=True, text=True)
    quiet = sum(float(m) for m in
                re.findall(r"silence_duration: ([\d.]+)", r.stderr))
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if not m:
        return 0.0
    secs = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return quiet / secs if secs else 0.0


def slugify(title):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", title.lower())).strip("-")


def load_state():
    if STATE.exists():
        eps = json.loads(STATE.read_text(encoding="utf-8"))
        # done = state entry AND the mp3 still on disk (old loop's site
        # build might clean unknown files; regenerate if so)
        return {e["day"]: e for e in eps
                if (REPO / "docs" / e["audioPath"].lstrip("/")).exists()}
    return {}


def save_state(eps):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(
        sorted(eps.values(), key=lambda e: -e["day"]), indent=1,
        ensure_ascii=False), encoding="utf-8")


def build_episode(day, info, eps):
    lesson = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", info["html"])).strip()
    # name the failing stage so the heartbeat says which one (HTTPError must
    # pass through untouched - the 429 quota-stop upstream depends on it)
    try:
        script = gen_script(day, info["title"], lesson)
    except urllib.error.HTTPError:
        raise
    except Exception as e:
        raise RuntimeError(f"script-{type(e).__name__}") from e
    try:
        pcm, rate, tts_model = gen_audio(script)
    except urllib.error.HTTPError:
        raise
    except Exception as e:
        raise RuntimeError(f"tts-{type(e).__name__}") from e
    slug = slugify(info["title"])
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    TRANS_DIR.mkdir(parents=True, exist_ok=True)
    tmp_mp3 = AUDIO_DIR / f"day-{day:03d}-{slug}.new.mp3"
    secs = encode_mp3(pcm, rate, tmp_mp3)
    # plausibility, not just reconciliation: duration alone reconciled fine
    # on an episode that was half dead air
    if not 180 <= secs <= 800:
        tmp_mp3.unlink()
        raise ValueError(f"audio duration {secs:.0f}s outside sanity range")
    sil = silence_ratio(tmp_mp3)
    wps = len(script.split()) / secs if secs else 0
    if sil > MAX_SILENCE_RATIO or wps < MIN_WORDS_PER_SEC:
        tmp_mp3.unlink()
        raise ValueError(f"audio failed plausibility: {sil:.0%} silence, "
                         f"{wps:.2f} words/sec ({len(script.split())} words "
                         f"in {secs:.0f}s) - TTS dropped content")
    # loudness gate (2026-08-08): a render whose volume wanders passed the
    # old gates and reached Brian's headphones. Post-normalization these
    # bounds hold for every good render; a violation means the render (or
    # the filter chain) is genuinely defective.
    li, lra = loudness(tmp_mp3)
    if lra > MAX_LRA or not MIN_I <= li <= MAX_I:
        tmp_mp3.unlink()
        raise ValueError(f"audio failed loudness gate: I={li:+.1f} LUFS, "
                         f"LRA={lra:.1f} LU - unstable render")
    size = tmp_mp3.stat().st_size
    final = AUDIO_DIR / f"day-{day:03d}-{slug}-{size}.mp3"
    tmp_mp3.rename(final)
    (TRANS_DIR / f"day-{day:03d}-{size}.txt").write_text(script, encoding="utf-8")
    date = info["date"] or datetime.now()
    eps[day] = {
        "day": day, "title": info["title"], "format": "two-host",
        "guid": f"two-host-day-{day:03d}",
        "publishedAt": date.strftime("%Y-%m-%dT%H:%M:%S"),
        "audioPath": f"/audio-v2/{final.name}",
        "transcriptPath": f"/transcripts-v2/day-{day:03d}-{size}.txt",
        "audioBytes": size, "durationSeconds": int(secs),
        "ttsModel": tts_model,
    }
    return secs


def rfc822(iso):
    return format_datetime(
        datetime.fromisoformat(iso).replace(tzinfo=timezone.utc))


def build_feed(eps):
    items = []
    for e in sorted(eps.values(), key=lambda x: -x["day"]):
        mins, secs = divmod(e["durationSeconds"], 60)
        items.append(f"""    <item>
      <title>Day {e['day']}: {escape(e['title'])}</title>
      <description>{escape(e['title'])} - AI Foundations day {e['day']}, as a conversation between Alex and Jordan.</description>
      <guid isPermaLink="false">{escape(e['guid'])}</guid>
      <pubDate>{rfc822(e['publishedAt'])}</pubDate>
      <itunes:episode>{e['day']}</itunes:episode>
      <enclosure url="{CDN}{e['audioPath']}" length="{e['audioBytes']}" type="audio/mpeg"/>
      <itunes:duration>{mins}:{secs:02d}</itunes:duration>
    </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>AI Foundations Daily</title>
    <link>{SITE}/</link>
    <language>en-us</language>
    <description>The AI Foundations course as a daily two-host conversation. Companion to the daily email and Kindle edition.</description>
    <itunes:author>AI Foundations</itunes:author>
    <itunes:type>serial</itunes:type>
    <itunes:image href="{SITE}/podcast-cover.png"/>
    <atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>
{chr(10).join(items)}
  </channel>
</rss>
"""
    (REPO / "docs" / "feed.xml").write_text(feed, encoding="utf-8")
    (REPO / "docs" / "feed.rss").write_text(feed, encoding="utf-8")


def build_index(eps):
    rows = []
    for e in sorted(eps.values(), key=lambda x: -x["day"]):
        mins, secs = divmod(e["durationSeconds"], 60)
        rows.append(
            f'<li><strong>Day {e["day"]}: {escape(e["title"])}</strong> '
            f'({mins}:{secs:02d}) <audio controls preload="none" '
            f'src="{e["audioPath"].lstrip("/")}"></audio> '
            f'<a href="{e["transcriptPath"].lstrip("/")}">transcript</a></li>')
    html = ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\"/>"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>"
            "<title>AI Foundations Daily</title>"
            "<style>body{font-family:Georgia,serif;max-width:44rem;margin:2rem auto;"
            "padding:0 1rem;line-height:1.5}li{margin:.8em 0}audio{width:100%;"
            "max-width:24rem;display:block;margin:.3em 0}</style></head><body>"
            "<h1>AI Foundations Daily</h1>"
            "<p>The AI Foundations course as a daily two-host conversation. "
            f"Subscribe by URL: <code>{SITE}/feed.xml</code></p><ul>"
            + "".join(rows) + "</ul></body></html>")
    (REPO / "docs" / "index.html").write_text(html, encoding="utf-8")


def build_preview_feed(eps):
    """Pre-cutover follow-along: the preview show Brian already follows
    carries every finished two-host episode while the main feed stays
    legacy. Deleted at cutover."""
    items = []
    for e in sorted(eps.values(), key=lambda x: -x["day"]):
        mins, secs = divmod(e["durationSeconds"], 60)
        items.append(f"""    <item>
      <title>Day {e['day']}: {escape(e['title'])}</title>
      <description>Two-host rebuild of AI Foundations day {e['day']}.</description>
      <guid isPermaLink="false">{escape(e['guid'])}</guid>
      <pubDate>{rfc822(e['publishedAt'])}</pubDate>
      <enclosure url="{CDN}{e['audioPath']}" length="{e['audioBytes']}" type="audio/mpeg"/>
      <itunes:duration>{mins}:{secs:02d}</itunes:duration>
    </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>AI Foundations - Format Preview</title>
    <link>{SITE}/</link>
    <language>en-us</language>
    <description>Follow-along feed for the two-host rebuild. New episodes appear here as the backfill progresses; the main feed flips over when all days are done.</description>
    <itunes:author>AI Foundations</itunes:author>
    <itunes:image href="{SITE}/podcast-cover.png"/>
{chr(10).join(items)}
  </channel>
</rss>
"""
    d = REPO / "docs" / "preview"
    d.mkdir(exist_ok=True)
    (d / "feed.xml").write_text(feed, encoding="utf-8")


def send_cutover_email():
    """One-time nudge when the feed flips - Brian has two manual steps."""
    import urllib.parse
    from email.message import EmailMessage
    gmail_dir = HOME / ".gmail-mcp"
    creds = json.loads((gmail_dir / "credentials.json").read_text())
    keys = json.loads((gmail_dir / "gcp-oauth.keys.json").read_text())["installed"]
    body = urllib.parse.urlencode({
        "client_id": keys["client_id"], "client_secret": keys["client_secret"],
        "refresh_token": creds["refresh_token"],
        "grant_type": "refresh_token"}).encode()
    req = urllib.request.Request(keys["token_uri"], data=body)
    with urllib.request.urlopen(req, timeout=30) as r:
        tok = json.loads(r.read())["access_token"]
    msg = EmailMessage()
    msg["To"] = msg["From"] = "brian@parkviewfamilyfarm.com"
    msg["Subject"] = "Podcast CUTOVER done - 2 steps for you"
    msg.set_content(
        "The two-host feed is now live (all course days rebuilt).\n\n"
        "1. DISABLE the ChatGPT-side daily audio job - it will fight this "
        "feed every morning until you do.\n"
        "2. In your podcast app: remove the show and re-add it by URL to "
        "clear stale cached episodes:\n"
        f"   {SITE}/feed.xml\n")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    req = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        data=json.dumps({"raw": raw}).encode(),
        headers={"Authorization": f"Bearer {tok}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["id"]


def git_sync():
    """Rebase onto the other writer BEFORE generating anything.

    2026-08-06: the ChatGPT-side job's commit deleted 10 two-host mp3s.
    publish() pulled that deletion in 28 seconds AFTER build_preview_feed()
    had already rendered the feed from memory, so 10 dead enclosures
    shipped. Syncing first means the other writer's state is visible to
    load_state() before any decision is made.
    """
    # --autostash: the previous run's heartbeat line is still uncommitted
    # at this point (it is written after publish() and committed by the
    # NEXT run), and a plain pull refuses on a dirty tree.
    r = subprocess.run(["git", "-C", str(REPO), "pull", "--rebase",
                        "--autostash"], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"WARNING: pre-run git pull failed: {r.stderr.strip()[:200]}")
    return r.returncode == 0


def feed_enclosures_on_disk():
    """Every enclosure OUR feeds advertise must exist on disk.

    Only validates enclosures served from SITE (our two-host output).
    The legacy feed's enclosures point at jsDelivr and belong to the
    ChatGPT-side job - not ours to gate on.
    """
    missing = []
    for name in ("feed.xml", "preview/feed.xml"):
        f = REPO / "docs" / name
        if not f.exists():
            continue
        try:
            root = ET.fromstring(f.read_text(encoding="utf-8"))
        except ET.ParseError as e:
            missing.append(f"{name}: UNPARSEABLE ({e})")
            continue
        for enc in root.findall(".//enclosure"):
            url = enc.get("url") or ""
            base = next((b for b in (CDN, SITE) if url.startswith(b)), None)
            if base is None:
                continue  # legacy feed's own URLs - the other writer's
            rel = url[len(base):].lstrip("/")
            if not (REPO / "docs" / rel).exists():
                missing.append(f"{name}->{rel}")
    return missing


def publish(msg):
    # commit FIRST, then rebase onto whatever the (pre-cutover) ChatGPT-side
    # job pushed this morning, then push - pulling before staging always
    # refuses (this run's outputs are unstaged at that point)
    subprocess.run(["git", "-C", str(REPO), "add", "-A"], check=True)
    r = subprocess.run(["git", "-C", str(REPO), "diff", "--cached", "--quiet"])
    committed = r.returncode != 0
    if committed:
        subprocess.run(["git", "-C", str(REPO), "commit", "-m", msg, "--quiet"],
                       check=True)
    ahead = subprocess.run(
        ["git", "-C", str(REPO), "rev-list", "--count", "@{u}..HEAD"],
        capture_output=True, text=True)
    if not committed and ahead.stdout.strip() == "0":
        return False
    subprocess.run(["git", "-C", str(REPO), "pull", "--rebase", "--quiet"],
                   check=True)
    # LAST GATE: the rebase may have just applied the other writer's
    # deletions. Never push a feed that advertises files we do not have.
    missing = feed_enclosures_on_disk()
    if missing:
        raise RuntimeError(
            f"refusing to push: {len(missing)} advertised enclosure(s) "
            f"missing after rebase, e.g. {missing[:3]}")
    subprocess.run(["git", "-C", str(REPO), "push", "--quiet"], check=True)
    return True


def main():
    run = "--run" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    started = datetime.now()

    if run:
        git_sync()  # see the other writer BEFORE deciding anything
    tok = gmail_token()
    canon = {int(k): v for k, v in json.loads(
        (HOME / "ai-foundations-kindle" / "canon.json")
        .read_text(encoding="utf-8")).items()}
    days, _ = select_days(tok, pull_copies(tok), canon)
    for day, info in load_recovered().items():
        days.setdefault(day, info)
    eps = load_state()
    missing = sorted(d for d in days if d not in eps)
    complete_before = not missing
    print(f"course days: 1-{max(days)} | episodes done: {len(eps)} | "
          f"missing: {missing or 'none'}")
    if not run:
        return

    # newest missing day first (today's episode ships same-morning even
    # mid-backfill), then oldest-first backfill
    queue = [missing[-1]] + missing[:-1] if missing else []
    made, fails, stopped = [], [], ""
    for day in queue[:limit] if limit else queue:
        if (datetime.now() - started).total_seconds() > RUN_CAP_SECONDS:
            stopped = f"run-cap {RUN_CAP_SECONDS}s reached at day {day}"
            print(f"  {stopped}")
            break
        try:
            secs = build_episode(day, days[day], eps)
            save_state(eps)
            made.append(day)
            print(f"  day {day}: OK ({secs:.0f}s)")
            time.sleep(15)  # stay under free-tier RPM
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code == 429:
                stopped = f"quota-429 at day {day}, resumes next run"
                print(f"  day {day}: {stopped}")
                break
            # only auth/permission errors are worth abandoning the run for;
            # anything else is this day's problem, not the fleet's
            print(f"  day {day}: HTTP {e.code} {body}")
            if e.code in (401, 403):
                stopped = f"HTTP-{e.code} at day {day}"
                break
            fails.append(f"{day}:HTTP{e.code}")
        except Exception as e:
            # keep the stage label (script-/tts-) rather than the bare
            # exception class, so the heartbeat names what actually broke
            fails.append(f"{day}:{e.args[0] if isinstance(e, RuntimeError) and e.args else type(e).__name__}")
            print(f"  day {day}: FAILED {e!r} - continuing")

    complete_now = not [d for d in days if d not in eps]
    # feed flips to two-host only once ALL days exist (cutover); after
    # that, every run keeps it regenerated (also self-heals clobbers)
    if complete_now:
        build_feed(eps)
        build_index(eps)
        # durable marker: fleet-watchdog only asserts the two-host format
        # once cutover has actually happened, and any later reversion to
        # the legacy feed (the ChatGPT-side job overwriting docs/feed.xml
        # each morning until Brian disables it) then reads as a failure
        marker = REPO / "data" / "cutover.json"
        if not marker.exists():
            marker.parent.mkdir(exist_ok=True)
            marker.write_text(json.dumps({
                "cutoverAt": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "days": len(eps)}, indent=1), encoding="utf-8")
        if not complete_before:
            try:
                send_cutover_email()
                print("cutover email sent")
            except Exception as e:
                print(f"cutover email FAILED: {e!r} - tell Brian manually")
    else:
        build_preview_feed(eps)
    label = f"day(s) {', '.join(map(str, made))}" if made else "feed refresh"
    try:
        pushed = "PUSHED" if publish(
            ("CUTOVER: two-host feed live - " if complete_now and not complete_before
             else "Two-host episodes: ") + label) else "no-push"
    except Exception as e:  # push can fail right after laptop wake (no
        pushed = f"PUSH-FAILED:{type(e).__name__}"  # network) - commit is
        print(f"publish failed: {e!r}")             # local, next run retries
    # HONEST STATUS TOKEN. This line is the watchdog's only build-layer
    # signal, so it must never read OK for a run that lost episodes or
    # failed to publish. quota-429 is deliberate pacing, NOT a failure.
    ondisk = len(load_state())
    if pushed.startswith("PUSH-FAILED") or ondisk != len(eps):
        status = "FAIL"
    elif fails or (made and pushed == "no-push"):
        status = "WARN"
    else:
        status = "OK"
    line = (f"{datetime.now():%Y-%m-%d %H:%M} {status} made:{len(made)} "
            f"ondisk:{ondisk} ledger:{len(eps)} "
            f"missing:{len([d for d in days if d not in eps])} "
            f"feed:{'two-host' if complete_now else 'legacy'} {pushed}"
            + (f" failed:{','.join(fails)}" if fails else "")
            + (f" stopped:{stopped}" if stopped else ""))
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


if __name__ == "__main__":
    main()
