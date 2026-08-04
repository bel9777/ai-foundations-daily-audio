# docs-state.md — ai-foundations-daily-audio (Claude-side handoff)

(Named docs-state.md, not docs/current-state.md, because docs/ is the
GitHub Pages webroot in this repo — nothing non-site goes in there.)

**Updated 2026-08-04 (takeover session). Status: BACKFILL 9/41 DONE,
paused at free-tier quota (~10 TTS calls/day), feed still legacy.**

Backfill run 1 (13:01): days 1-9 generated and pushed, quota-429 at
day 10. At ~9-10/day the remaining 32 finish ~Aug 8-9, then cutover
auto-flips and emails Brian his 2 steps (send_cutover_email). Enabling
billing on the Gemini key (~$1-2 total) would finish it in one manual
`py podcast.py --run`. Daily runs generate the NEWEST missing day first,
so current-day episodes ship same-morning even mid-backfill.

## What happened today

- Brian rated the old single-voice narration "not great"; picked the
  two-host conversational format, Gemini (no-subscription) stack.
- Prototype Day 41 episode approved (voices Puck/Sulafat). His one catch:
  the dialogue dropped the lesson's hands-on exercise → homework beat is
  now mandatory in the script spec (CLAUDE.md rule 3).
- `podcast.py` built: canon-adjudicated day selection (imported from
  ai-foundations-kindle), dialogue gen + multi-speaker TTS + mp3 + feed
  build, idempotent, quota-tolerant, two-writer-safe (CLAUDE.md rule 1).
- Full 41-episode backfill launched ~11:45. Daily task registered
  (7:45, battery-safe). Watchdog rows: live-feed check (pre-existing) +
  _RUN-LOG freshness.
- `docs/preview/` holds the approved format sample (temporary).

## Cutover checklist (the current arc — finish this)

1. Backfill reaches missing:none (check `_RUN-LOG.md` / `py podcast.py`).
2. The same run auto-flips docs/feed.xml + index.html (commit "CUTOVER:").
3. Verify live: feed shows Day-N two-host items, newest mp3 HEADs 200.
4. Brian re-adds the main feed in his podcast app (clears pre-Aug-1
   broken cached episodes too).
5. **Brian disables the ChatGPT-side daily audio job** — until then every
   morning ~9:11 the old job may push old-format episodes/feed; my next
   7:45 run re-flips. Nag him if this lingers.
6. Delete docs/preview/ and note the legacy app/ code as retired.

## Known rough edges

- Old-format mp3s remain in docs/audio/ (harmless, unreferenced after
  cutover; cleaning them is optional and shrinks nothing in git history).
- Free-tier TTS quota unknown — if the backfill stops on 429, the daily
  7:45 task continues it automatically each day until done; enabling
  billing on the Gemini key (~$1–2 total) would finish it in one run.
- Episode pubDates = original lesson email dates (so apps sort history
  correctly); Day 4 (recovered, no email) gets the recovered date.
