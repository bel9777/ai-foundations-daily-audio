"""One-time catalog-wide loudness normalization (2026-08-08).

Brian reported Day 1 audio "goes in and out and can barely be heard".
EBU R128 audit confirmed 22 of 45 episodes with LRA > 10 LU (produced
podcasts: 4-7) and episode-to-episode integrated loudness spanning
-13.9 to -26.4 LUFS. Chain: dynaudnorm evens intra-file swings, loudnorm
targets podcast standard (-16 LUFS, TP -1.5, LRA 7).

Per episode: normalize -> MEASURE -> accept only if LRA <= 8.5 and
-19.5 <= I <= -13.5 -> rename to the new byte size -> update ledger.
A file that fails the post-check keeps its ORIGINAL audio and is
reported - no silent regressions. Feed rebuilds and publishes at the end.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import podcast

REPO = Path(__file__).resolve().parent
AUDIO = REPO / "docs" / "audio-v2"
TRANS = REPO / "docs" / "transcripts-v2"
FILTERS = "dynaudnorm=f=300:g=31:p=0.95,loudnorm=I=-16:TP=-1.5:LRA=7"


def measure(path):
    r = subprocess.run([str(podcast.FFMPEG), "-i", str(path), "-af",
                        "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True)
    tail = r.stderr[-2000:]
    i = float(re.search(r"I:\s*(-?[\d.]+) LUFS", tail).group(1))
    lra = float(re.search(r"LRA:\s*([\d.]+) LU", tail).group(1))
    d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    secs = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
    return i, lra, secs


def main():
    eps = podcast.load_state()
    done, kept = [], []
    for day in sorted(eps):
        e = eps[day]
        src = REPO / "docs" / e["audioPath"].lstrip("/")
        tmp = AUDIO / f"day-{day:03d}.norm.tmp.mp3"
        subprocess.run([str(podcast.FFMPEG), "-y", "-loglevel", "error",
                        "-i", str(src), "-af", FILTERS,
                        "-codec:a", "libmp3lame", "-b:a", "96k", str(tmp)],
                       check=True)
        i, lra, secs = measure(tmp)
        if lra > 8.5 or not -19.5 <= i <= -13.5:
            tmp.unlink()
            kept.append((day, i, lra))
            print(f"  day {day}: post-check FAILED (I={i:+.1f}, LRA={lra:.1f})"
                  " - keeping original")
            continue
        size = tmp.stat().st_size
        slug = re.sub(r"^day-\d+-(.+)-\d+\.mp3$", r"\1", src.name)
        final = AUDIO / f"day-{day:03d}-{slug}-{size}.mp3"
        tmp.rename(final)
        if final != src:
            src.unlink()
        # transcript rename keeps the size-keyed convention aligned
        old_tr = REPO / "docs" / e["transcriptPath"].lstrip("/")
        new_tr = TRANS / f"day-{day:03d}-{size}.txt"
        if old_tr.exists() and old_tr != new_tr:
            old_tr.rename(new_tr)
        e.update(audioPath=f"/audio-v2/{final.name}",
                 transcriptPath=f"/transcripts-v2/{new_tr.name}",
                 audioBytes=size, durationSeconds=int(secs),
                 normalized=True)
        podcast.save_state(eps)
        done.append((day, i, lra))
        print(f"  day {day}: OK  I={i:+.1f} LUFS  LRA={lra:.1f} LU")

    podcast.build_feed(eps)
    podcast.build_index(eps)
    missing = podcast.feed_enclosures_on_disk()
    print(f"\nnormalized {len(done)}, kept-original {len(kept)}, "
          f"enclosure gate: {missing or 'CLEAN'}")
    if missing:
        sys.exit("refusing to publish")
    if kept:
        print("NEEDS ATTENTION (kept original):",
              json.dumps([{"day": d, "I": i, "LRA": l} for d, i, l in kept]))
    print("pushed:", podcast.publish(
        "Normalize catalog loudness: dynaudnorm+loudnorm to -16 LUFS "
        "(22 of 45 episodes measured unstable, LRA up to 23.6)"))


if __name__ == "__main__":
    main()
