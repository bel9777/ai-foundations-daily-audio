"""Force-regenerate a two-host episode that the ledger thinks is done.

podcast.py skips any day whose ledger entry exists and whose mp3 is on
disk, so a BAD episode (e.g. Day 43's 48% dead air) never self-heals.
This regenerates in a scratch slot and swaps in ONLY on success, so a
quota 429 or another silent render leaves the existing file untouched.

Usage:  py regen_episode.py 43 [6 ...]
"""

import json
import sys
from pathlib import Path

import podcast

HOME = Path.home()
REPO = Path(__file__).resolve().parent


def main():
    days = [int(a) for a in sys.argv[1:] if a.isdigit()]
    if not days:
        sys.exit(__doc__)

    tok = podcast.gmail_token()
    canon = {int(k): v for k, v in json.loads(
        (HOME / "ai-foundations-kindle" / "canon.json")
        .read_text(encoding="utf-8")).items()}
    lessons, _ = podcast.select_days(tok, podcast.pull_copies(tok), canon)
    for d, info in podcast.load_recovered().items():
        lessons.setdefault(d, info)

    eps = podcast.load_state()
    for day in days:
        if day not in lessons:
            print(f"day {day}: no lesson source - skipped")
            continue
        old = eps.get(day)
        old_mp3 = (REPO / "docs" / old["audioPath"].lstrip("/")) if old else None
        scratch = dict(eps)
        scratch.pop(day, None)
        try:
            secs = podcast.build_episode(day, lessons[day], scratch)
        except Exception as e:
            print(f"day {day}: regen FAILED ({e!r}) - existing file untouched")
            continue
        new = scratch[day]
        # only now retire the old file
        if old_mp3 and old_mp3.exists() and old_mp3.name != Path(
                new["audioPath"]).name:
            old_mp3.unlink()
            old_tr = REPO / "docs" / old["transcriptPath"].lstrip("/")
            if old_tr.exists():
                old_tr.unlink()
        eps[day] = new
        podcast.save_state(eps)
        print(f"day {day}: regenerated OK ({secs:.0f}s) -> {new['audioPath']}")

    eps = podcast.load_state()
    podcast.build_preview_feed(eps)
    missing = podcast.feed_enclosures_on_disk()
    print(f"feed rebuilt: {len(eps)} episodes | gate: {missing or 'NONE MISSING'}")
    if missing:
        sys.exit("refusing to publish - advertised enclosures missing")
    print("pushed:", podcast.publish(
        f"Regenerate episode(s) {', '.join(map(str, days))} (failed "
        f"plausibility gate: silence/words-per-second)"))


if __name__ == "__main__":
    main()
