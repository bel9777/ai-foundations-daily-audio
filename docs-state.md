# docs-state.md — ai-foundations-daily-audio (Claude-side handoff)

## 2026-08-06 — incident session (READ THIS FIRST)

Brian asked why GitHub was emailing build failures. An 11-agent
investigation (5 angles, each adversarially verified) found the notices
were mostly noise and something worse underneath.

**Pages build failures = GitHub's outage, NOT this repo.** Proven three
ways: the largest artifact this repo ever produced (277 MB) deployed on
the FIRST poll in 5.2s the day before, while a 47 MB SMALLER one timed
out; the build+upload phases were normal in both failures (all ~600s of
delay is after the artifact is handed off); and an unrelated tiny repo
(pvf-order-planner) failed identically the same morning. GitHub then
declared "Pages - Deployment Lag" (15:03Z). **Do not delete or re-encode
audio to "fix" this** — site is ~30% of the 1 GB limit, regression across
16 loaded deploys gives ~0.073 s/MiB, i.e. an ~8 GB artifact would be
needed to hit the 600s timeout.
One nuance worth keeping: the two failures were NOT the same. Run
31103528916 polled `deployment_queued` 114x and never deployed — the
12:55Z Day 43 publish sat undeployed ~1h57m (a TRUE positive). Run
31111812167 polled `deployment_in_progress` and landed ~3.5 min after the
action gave up (false alarm).

**The real damage: 10 two-host episodes were deleted** by the
ChatGPT-side job's commit 39fefa3 (days 1-9 + 41, plus transcripts and
the preview mp3 — 24 files), and the preview feed advertised 21 episodes
while 10 returned 404. RESTORED this session from 67a7259, byte-identical
(commit 9f251e4). See CLAUDE.md hard rule 0 for the mechanism and the
restore recipe. Recurrence so far: 1 of 3 legacy commits.

**Day 43 is broken and will never self-heal**: 662s file with a single
contiguous ~320s block of true digital silence (-85.5 dB) starting ~4:10;
transcript is a healthy 1,012 words, so TTS dropped ~5.5 min. The
duration-only gate could not see it (duration comes from PCM byte count,
and silence is bytes). Day 11 has 77s of tail silence (unconfirmed
whether content is missing — 21% ratio, worth one listen before spending
quota); Day 16 has 15.5s trailing dead air (cosmetic, leave it).
NEEDS A FORCED RE-RENDER: delete its ledger entry + mp3, then
`py podcast.py --run --limit 1`.

**Code hardening shipped this session** (podcast.py): `git_sync()` before
anything is generated; `feed_enclosures_on_disk()` as a hard pre-push
gate; honest OK/WARN/FAIL heartbeat token with `ondisk:N/ledger:M` and
finish-time stamping (it previously hardcoded " OK " and reported success
on a run with 3 TimeoutErrors and 10 lost episodes); split Gemini
timeouts (text 120s / TTS 600s) with the failing stage named in the
heartbeat; a 3-hour run cap; and a plausibility gate replacing
duration-only (rejects >10% silence or <2.0 words/sec).

**Watchdog hardening shipped** (fleet-watchdog): `pages_landed` compares
live bytes vs origin/main bytes with a 30-min in-flight grace — this is
the ONLY signal that separated the healthy repo from the genuinely stale
one (build status reported "errored" for both). `feed_enclosures` HEADs
every episode in both feeds and compares served length vs declared length
(the 404 page is a clean 37 KB HTML 200, so status alone would pass).
`heartbeat` parses the status token and escalates a day failing on 3
consecutive runs to FAIL. Plus a run deadline so a slow probe can never
suppress the daily email (silence is the dead-man's switch).

**STILL OPEN — Brian's call before cutover:** the main feed's audio is
served from **jsDelivr** (`cdn.jsdelivr.net/gh/...@main/docs/audio/`),
which is why today's Pages outage never touched his listening. But
`build_feed()` emits `SITE` (GitHub Pages) for two-host enclosures, so
cutover silently moves all audio delivery onto the service that failed
twice today, plus a 100 GB/month bandwidth cap. Recommend keeping
jsDelivr (counter-consideration: its @main ref carries a 12h
`s-maxage`, unmonitored edge staleness on a daily show).


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
