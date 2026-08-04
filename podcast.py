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
TTS_MODEL = "gemini-3.1-flash-tts-preview"
FFMPEG = (HOME / r"AppData\Local\Microsoft\WinGet\Packages"
               r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
               r"\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe")

HOST, EXPERT = "Alex", "Jordan"
VOICE_HOST, VOICE_EXPERT = "Puck", "Sulafat"
SITE = "https://bel9777.github.io/ai-foundations-daily-audio"
STATE = REPO / "data" / "two-host-episodes.json"
AUDIO_DIR = REPO / "docs" / "audio-v2"
TRANS_DIR = REPO / "docs" / "transcripts-v2"
RUN_LOG = REPO / "_RUN-LOG.md"


def gapi(path, payload, timeout=300):
    req = urllib.request.Request(
        f"{GBASE}/{path}", data=json.dumps(payload).encode(),
        headers={"x-goog-api-key": KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


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
        "generationConfig": {"temperature": 0.8}})
    script = resp["candidates"][0]["content"]["parts"][0]["text"].strip()
    script = re.sub(r"^```.*$", "", script, flags=re.M).strip()
    lines = [ln for ln in script.splitlines() if ln.strip()]
    good = [ln for ln in lines if re.match(rf"^({HOST}|{EXPERT}):", ln.strip())]
    if len(good) < len(lines) - 2 or len(script.split()) < 500:
        raise ValueError(f"script failed QA: {len(good)}/{len(lines)} dialogue "
                         f"lines, {len(script.split())} words")
    return "\n".join(good)


def gen_audio(script):
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
                    {"prebuiltVoiceConfig": {"voiceName": VOICE_EXPERT}}}]}}}})
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
                    "-codec:a", "libmp3lame", "-b:a", "96k", str(out_path)],
                   check=True)
    tmp.unlink()
    return len(pcm) / (rate * 2)


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
    script = gen_script(day, info["title"], lesson)
    pcm, rate = gen_audio(script)
    slug = slugify(info["title"])
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    TRANS_DIR.mkdir(parents=True, exist_ok=True)
    tmp_mp3 = AUDIO_DIR / f"day-{day:03d}-{slug}.new.mp3"
    secs = encode_mp3(pcm, rate, tmp_mp3)
    if not 180 <= secs <= 800:
        tmp_mp3.unlink()
        raise ValueError(f"audio duration {secs:.0f}s outside sanity range")
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
      <enclosure url="{SITE}{e['audioPath']}" length="{e['audioBytes']}" type="audio/mpeg"/>
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
      <enclosure url="{SITE}{e['audioPath']}" length="{e['audioBytes']}" type="audio/mpeg"/>
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


def publish(msg):
    subprocess.run(["git", "-C", str(REPO), "pull", "--rebase", "--quiet"],
                   check=False)
    subprocess.run(["git", "-C", str(REPO), "add", "-A"], check=True)
    r = subprocess.run(["git", "-C", str(REPO), "diff", "--cached", "--quiet"])
    if r.returncode == 0:
        return False
    subprocess.run(["git", "-C", str(REPO), "commit", "-m", msg, "--quiet"],
                   check=True)
    subprocess.run(["git", "-C", str(REPO), "push", "--quiet"], check=True)
    return True


def main():
    run = "--run" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    now = datetime.now()

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
    made, stopped = [], ""
    for day in queue[:limit] if limit else queue:
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
            print(f"  day {day}: HTTP {e.code} {body}")
            stopped = f"HTTP-{e.code} at day {day}"
            break
        except Exception as e:
            print(f"  day {day}: FAILED {e!r} - continuing")

    complete_now = not [d for d in days if d not in eps]
    # feed flips to two-host only once ALL days exist (cutover); after
    # that, every run keeps it regenerated (also self-heals clobbers)
    if complete_now:
        build_feed(eps)
        build_index(eps)
        if not complete_before:
            try:
                send_cutover_email()
                print("cutover email sent")
            except Exception as e:
                print(f"cutover email FAILED: {e!r} - tell Brian manually")
    else:
        build_preview_feed(eps)
    label = f"day(s) {', '.join(map(str, made))}" if made else "feed refresh"
    pushed = publish(
        ("CUTOVER: two-host feed live - " if complete_now and not complete_before
         else "Two-host episodes: ") + label)
    line = (f"{now:%Y-%m-%d %H:%M} OK made:{len(made)} total:{len(eps)} "
            f"missing:{len([d for d in days if d not in eps])} "
            f"feed:{'two-host' if complete_now else 'legacy'} "
            f"{'PUSHED' if pushed else 'no-push'}"
            + (f" stopped:{stopped}" if stopped else ""))
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


if __name__ == "__main__":
    main()
