import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const docs = path.join(root, "docs");

test("builds a mobile-ready static listening page for GitHub Pages", async () => {
  const page = await readFile(path.join(docs, "index.html"), "utf8");
  const css = await readFile(path.join(docs, "styles.css"), "utf8");

  assert.match(page, /<meta name="viewport"/);
  assert.match(page, /Email ↔ Kindle ↔ Podcast/);
  assert.match(page, /Copy Apple Podcasts feed/);
  assert.match(page, /Prompting as Interface Design/);
  assert.match(page, /podcast-cover\.png/);
  assert.match(css, /@media \(max-width: 640px\)/);
  assert.doesNotMatch(css, /@import "tailwindcss"/);
});

test("builds an Apple-compatible public feed with matching local media", async () => {
  const feed = await readFile(path.join(docs, "feed.rss"), "utf8");
  assert.match(
    feed,
    /https:\/\/bel9777\.github\.io\/ai-foundations-daily-audio\/feed\.rss/,
  );
  assert.match(feed, /<itunes:category text="Education">/);
  assert.match(feed, /<itunes:episode>35<\/itunes:episode>/);
  assert.match(feed, /Kindle chapter Day 35/);
  assert.match(feed, /urn:ai-foundations:gmail:19fada8d1b86a68f/);
  assert.match(
    feed,
    /https:\/\/cdn\.jsdelivr\.net\/gh\/bel9777\/ai-foundations-daily-audio@main\/docs\/audio\//,
  );
  assert.doesNotMatch(feed, /chatgpt\.site/);

  const enclosurePattern =
    /<enclosure url="[^"]+\/audio\/([^"]+\.mp3)" length="(\d+)" type="audio\/mpeg" \/>/g;
  const enclosures = [...feed.matchAll(enclosurePattern)];
  assert.equal(enclosures.length, 2);

  for (const enclosure of enclosures) {
    const media = await stat(path.join(docs, "audio", enclosure[1]));
    assert.equal(media.size, Number(enclosure[2]));
  }
});
