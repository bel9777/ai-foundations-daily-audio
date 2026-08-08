# docs-state.md — ai-foundations-daily-audio (Claude-side handoff)

## 2026-08-08 (later) — LOUDNESS REMEDIATION, catalog verified stable

Brian reported Day 1 "goes in and out, can barely be heard". EBU R128
audit: 22 of 45 episodes LRA > 10 LU (max 23.6), levels spanning -13.9
to -26.4 LUFS. Every fallback-model (2.5-flash) render was stable; the
long 3.1-preview renders wobbled. Actions, all shipped:
- `normalize_catalog.py`: dynaudnorm + loudnorm (-16 LUFS/TP -1.5/LRA 7)
  across the catalog, per-file post-measurement, originals kept on any
  post-check failure (no silent regressions).
- Days 4 + 11 (unsalvageable by filtering) re-rendered fresh.
- podcast.py now normalizes at encode time, gates every render on
  loudness (LRA <= 8.5, -19.5 <= I <= -13.5), and 2.5-flash is PRIMARY.
- docs/preview/ deleted per the cutover checklist (Brian's steps done);
  regen_episode.py rebuilds the MAIN feed post-cutover.
FINAL AUDIT: 45/45 episodes, LRA median 4.9 / max 8.1, zero over 10.
Live feed verified: live==origin, 45 items days 1-45, 45/45 enclosures
HTTP 200. Remaining subjective check = Brian's ears.

## 2026-08-08 07:28 — CUTOVER DONE, VERIFIED

All 44 days two-host. Main feed flipped, deployed, and PROVEN live:
44/44 enclosures HTTP 200, live bytes == origin/main, cutover email sent,
`data/cutover.json` marker written, all three post-cutover watchdog
checks OK. Day 33 rendered via the new CHUNKED fallback (4 TTS calls
concatenated; passed silence/wps gates; seams not yet human-audited).
**Waiting on Brian: disable the ChatGPT-side job** (its ~9:11 daily push
reverts feed.xml to legacy until the next 7:45 re-flip — the watchdog
feed_format FAIL each morning is the deliberate nag) **and re-add the
feed by URL in his app.** Then delete docs/preview/ per the checklist.

## Previous status (2026-08-07): 43 of 44 — superseded above

Verified 09:38: preview feed carries 43 items, all 43 enclosures return
HTTP 200 via the CDN, coverage = days 1-32 and 34-44. **Only day 33 is
missing** (its render died on `tts-URLError`, then both TTS quota buckets
hit 429). Tomorrow's 07:45 run makes day 33 + the new day 45; when
nothing is missing, `complete_now` flips the main feed to two-host and
fires `send_cutover_email()`. Nothing else is pending.

Resilience added after this morning's partial run: `gapi()` retries
transient 5xx (a single 503 at day 33 had killed a whole run and left 8
episodes unmade), only 401/403 abandons a run, and the heartbeat keeps
the stage label (`33:tts-URLError`) instead of a bare exception class.
Quota is PER MODEL — `TTS_MODELS` falls through
gemini-3.1-flash-tts-preview to gemini-2.5-flash-preview-tts, roughly
doubling free-tier throughput. Note a small probe can succeed while a
full episode 429s: the remaining allowance is token-based, so "the model
answered" does NOT mean an episode will render.

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

**Resolved same session:** Day 43 and Day 6 force-regenerated via the new
`regen_episode.py` (regenerates into a scratch slot, swaps in ONLY on
success, so a 429 or another silent render leaves the existing file
alone). Both now 0% silence / ~2.85 wps with all four required beats
including homework. All 21 preview enclosures verified 200 via the CDN.
Audio delivery moved to jsDelivr, which also settles the cutover hosting
question below in favour of the CDN.

**Pending on GitHub, nothing to do:** Pages was in MAJOR OUTAGE at end of
session, so the updated feed documents (which live on Pages) had not
deployed. Audio is unaffected — it comes from the CDN. When Pages
recovers, the preview feed's enclosures flip to CDN URLs automatically on
the next deploy; no action needed.

**STILL OPEN — Brian's call:** the main feed's audio is
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
