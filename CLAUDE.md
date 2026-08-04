# CLAUDE.md — ai-foundations-daily-audio

Canonical agent rules. Read `docs/current-state.md` next.

## What this is

The AI Foundations podcast: GitHub Pages site + RSS feed at
`https://bel9777.github.io/ai-foundations-daily-audio/feed.xml`.
As of 2026-08-04, episodes are generated CLAUDE-SIDE by `podcast.py`
(two-host dialogue via Gemini text + multi-speaker TTS), Task Scheduler
`AI Foundations Podcast daily` at 7:45. The Next.js/npm machinery in
`app/` etc. is the LEGACY ChatGPT-side pipeline (single-voice narration),
retired at cutover — do not run or extend it.

## Hard rules

1. **Two-writer safety until cutover is confirmed**: podcast.py writes
   ONLY `docs/audio-v2/`, `docs/transcripts-v2/`,
   `data/two-host-episodes.json`, `_RUN-LOG.md`. It must not touch
   `docs/feed.xml` / `feed.rss` / `index.html` until every course day has
   a two-host episode; that completion flips the feed in one commit (the
   commit message starts with CUTOVER). Brian must disable the
   ChatGPT-side daily audio job at that moment — until he confirms, the
   old job may regenerate docs/ and my code self-heals (an episode counts
   as done only if its mp3 exists on disk).
2. **HARD dependency on `~\ai-foundations-kindle`** (canon.json +
   build.py selection logic — the single adjudication of what each course
   day IS). Import failure must stay FATAL, never fail-soft.
3. **Episode spec is Brian-approved (2026-08-04)**: Alex (Puck, curious)
   + Jordan (Sulafat, expert); hook → concepts + example → knowledge
   check as quiz → homework beat (the lesson's hands-on exercise — it was
   dropped once and Brian caught it) → tomorrow tease; 900–1050 words.
   Change voices/format only on Brian's say-so.
4. **Gemini key**: `~\.ai-keys\gemini-api-key.txt` — never commit, never
   log. Free-tier quota (429) pauses the backfill by design; the next
   run resumes. Models: `gemini-flash-latest` + `gemini-3.1-flash-tts-preview`
   (re-discover via the models endpoint if either 404s — entitlements
   shift; `gemini-2.5-flash` lists but 404s on this key).
5. **Feed titles are load-bearing**: `Day N: Title` — fleet-watchdog's
   live-feed check parses `Day (\d+)`. Keep the format.
6. `docs/preview/` is a throwaway format-preview feed — delete after
   cutover.

## Ops

- Daily task 7:45 (battery-safe flags). Heartbeat `_RUN-LOG.md`:
  `... OK made:N total:N missing:N feed:two-host|legacy PUSHED`.
- Watched by fleet-watchdog twice: `_RUN-LOG.md` freshness (build layer)
  + live feed.xml newest-day/mp3 HEAD (end-to-end layer).
- Unattended push relies on Windows Credential Manager's stored GitHub
  credentials (verified working from this clone).
