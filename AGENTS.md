# AGENTS.md

All agent rules for this repo live in **CLAUDE.md** — read that first, then
`docs-state.md` for the live handoff (NOT docs/current-state.md; `docs/` is
the GitHub Pages webroot and holds only site files).

The live Claude-side pipeline is `podcast.py`. The `app/` + `scripts/`
Next.js code is the ChatGPT-side pipeline — it is **still running daily
until cutover**, despite older wording here calling it "retired". Do not
run it locally: `scripts/build-github-pages.mjs:80` does
`rm -rf docs` and rebuilds from `public/audio/` + `public/transcripts/`,
which are gitignored and absent in this clone, so `npm test` (which runs
`build:pages`) wipes ~285 MB including both feeds and both audio trees.
