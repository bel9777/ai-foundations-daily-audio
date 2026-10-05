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

0. **THE OTHER WRITER DELETES THINGS.** On 2026-08-06 the ChatGPT-side
   job's commit 39fefa3 deleted 24 files — days 1-9 + 41 from
   docs/audio-v2, their transcripts, and the preview mp3 — and podcast.py
   published a feed advertising them anyway (10 live 404s) because it had
   built the feed in memory BEFORE its rebase pulled the deletion in.
   Mechanism is still UNPROVEN (that job runs in a clone we cannot
   inspect); strongest fingerprint is stale-base-plus-rebase, with
   `scripts/build-github-pages.mjs:80` (`rm -rf docs`, sources gitignored
   and absent here) a second live footgun — never run `npm test` or
   `build:pages` in this clone. Mitigations now in code: `git_sync()`
   before anything is generated, and `feed_enclosures_on_disk()` as a
   hard pre-push gate. If episodes vanish again, RESTORE FROM GIT
   (`git checkout <commit> -- docs/audio-v2 docs/transcripts-v2`) rather
   than regenerating: filenames embed byte size, so restored blobs are
   byte-identical and already-published enclosure URLs keep resolving,
   at zero Gemini quota.

1. **(HISTORICAL - cutover done 2026-08-08; post-cutover the main feed
   is rebuilt every run from all episodes on disk, fixed 2026-10-05 after
   it froze at Day 51 for 7 weeks.)** Two-writer safety until cutover: podcast.py writes
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
3. **Episode spec is Brian-approved (2026-08-04, v2 shapes approved
   2026-10-05)**: Alex (Puck, curious) + Jordan (Sulafat, expert). Lesson
   days: Frontier-Note cold open (when the lesson has one) → hook →
   concepts + example → quiz → homework beat (it was dropped once and
   Brian caught it) → tomorrow tease. `episode_shape()` switches on title
   prefix: "Lab:" walkthrough, "This Week in AI" news show, "Weekly
   Review" quiz show. 900–1050 words. Change voices/format only on
   Brian's say-so.
4. **Gemini key**: `~\.ai-keys\gemini-api-key.txt` — never commit, never
   log. Free-tier quota (429) pauses the backfill by design; the next
   run resumes. Models (2026-10-05): TEXT_MODELS chain led by
   `gemini-3.8-flash`; TTS PRIMARY `gemini-3.8-flash-tts` (GA; needs one
   part per line tagged `speechMetadata.speaker`, returns WAV) with the
   two previews as fallback; fall-through on 429 AND 5xx. Re-discover via
   the models endpoint if any 404 (`gemini-2.5-flash` lists but 404s).
   Network: IPv4 forced via the kindle build.py import + per-user
   usercustomize.py (IPv6 blackholed on this laptop).
5. **Feed titles are load-bearing**: `Day N: Title` — fleet-watchdog's
   live-feed check parses `Day (\d+)`. Keep the format.
6. `docs/preview/` is the pre-cutover follow-along feed Brian listens to.
   It is NOT disposable while the backfill runs — delete only at cutover.
   (Earlier docs called it "a throwaway... safe to delete"; that wording
   is what made deleting two-host output look sanctioned.)
7. **Never read `data/two-host-episodes.json` directly** to judge progress
   — it can hold entries whose mp3s no longer exist (it read 21 against 11
   real files on 2026-08-06). Always resolve through `load_state()`, which
   filters by file existence on disk. `ondisk:N/ledger:M` in the heartbeat
   surfaces any divergence.
8. **Audio is served from GitHub Pages since 2026-10-05** (`AUDIO_BASE`
   in podcast.py). jsDelivr had served it since August but failed 42/102
   enclosures (404/503/timeouts, old files too) once the repo's audio hit
   ~650 MB; Pages served 102/102. Pages' 1 GB site limit: docs/ ~650 MB,
   +~4.5 MB/day, so prune (e.g. the retired legacy docs/audio, 233 MB)
   before ~Jan 2027. Re-check every enclosure before ever flipping back.

9. **Weekly collections** (`weekly.py`, 2026-10-05): each Mon-Sun week as
   one chaptered mp3 in `docs/weekly.xml`; audio on the GitHub release
   `weekly-collections` (NOT Pages - 1 GB cap). Recompiles when a week's
   episode set changes. Called from `podcast.py --run`; failures show as
   `weekly-FAILED` in the heartbeat and never block the daily episode.
   Main feed is `itunes:type episodic` (serial made apps list oldest first).

## Ops

- Daily task 7:45 (battery-safe flags). Heartbeat `_RUN-LOG.md`:
  `... OK made:N total:N missing:N feed:two-host|legacy PUSHED`.
- Watched by fleet-watchdog twice: `_RUN-LOG.md` freshness (build layer)
  + live feed.xml newest-day/mp3 HEAD (end-to-end layer).
- Unattended push relies on Windows Credential Manager's stored GitHub
  credentials (verified working from this clone).
