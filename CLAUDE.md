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
6. `docs/preview/` is the pre-cutover follow-along feed Brian listens to.
   It is NOT disposable while the backfill runs — delete only at cutover.
   (Earlier docs called it "a throwaway... safe to delete"; that wording
   is what made deleting two-host output look sanctioned.)
7. **Never read `data/two-host-episodes.json` directly** to judge progress
   — it can hold entries whose mp3s no longer exist (it read 21 against 11
   real files on 2026-08-06). Always resolve through `load_state()`, which
   filters by file existence on disk. `ondisk:N/ledger:M` in the heartbeat
   surfaces any divergence.
8. **The main feed's audio is served by jsDelivr, not Pages.** Every
   legacy enclosure is `cdn.jsdelivr.net/gh/bel9777/ai-foundations-daily-audio@main/docs/audio/...`,
   which is why the 2026-08-06 Pages outage never touched Brian's
   listening. `build_feed()` currently emits `SITE` (GitHub Pages) for
   two-host enclosures, so **cutover silently migrates all audio delivery
   off the CDN that works onto the service that failed** — plus Pages'
   100 GB/month bandwidth cap. This is Brian's decision and is flagged in
   docs-state.md; do not let cutover happen without it being made.

## Ops

- Daily task 7:45 (battery-safe flags). Heartbeat `_RUN-LOG.md`:
  `... OK made:N total:N missing:N feed:two-host|legacy PUSHED`.
- Watched by fleet-watchdog twice: `_RUN-LOG.md` freshness (build layer)
  + live feed.xml newest-day/mp3 HEAD (end-to-end layer).
- Unattended push relies on Windows Credential Manager's stored GitHub
  credentials (verified working from this clone).
