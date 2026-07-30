# AI Foundations Daily Audio

The public-by-URL, unlisted listening site and RSS feed for Brian's AI
Foundations course.

Each podcast episode is generated from the same canonical lesson record used by
the daily email and Kindle library:

- `day` becomes the email day, Kindle chapter number, and podcast episode number.
- `title` is shared across all three formats.
- `source_message_id` becomes the podcast episode's permanent RSS GUID.

Run `npm run sync:course` before building to copy available audio, generate
transcripts, and refresh `data/episodes.json`.

Run `npm run build:pages` to create the public GitHub Pages site and
Apple-compatible static RSS feed in `docs/`.
