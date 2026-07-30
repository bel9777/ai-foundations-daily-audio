import assert from "node:assert/strict";
import test from "node:test";

const workerUrl = new URL("../dist/server/index.js", import.meta.url);

async function render(pathname, accept = "text/html") {
  const url = new URL(workerUrl);
  url.searchParams.set("test", `${process.pid}-${Date.now()}-${pathname}`);
  const { default: worker } = await import(url.href);

  return worker.fetch(
    new Request(`https://example.com${pathname}`, {
      headers: { accept },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("renders the course listening page with canonical lesson mapping", async () => {
  const response = await render("/");
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /AI Foundations/);
  assert.match(html, /Email.*Kindle.*Podcast/s);
  assert.match(html, /Prompting as Interface Design/);
  assert.match(html, /What AI Is \(and What It Is Not\)/);
  assert.match(html, /podcast-cover\.png/);
});

test("serves a podcast RSS feed with absolute media URLs and stable Gmail GUIDs", async () => {
  const response = await render("/feed.xml", "application/rss+xml");
  assert.equal(response.status, 200);
  assert.match(
    response.headers.get("content-type") ?? "",
    /^application\/rss\+xml\b/i,
  );

  const xml = await response.text();
  assert.match(xml, /<rss version="2\.0"/);
  assert.match(xml, /<itunes:category text="Education">/);
  assert.match(xml, /<guid isPermaLink="false">urn:ai-foundations:gmail:/);
  assert.match(
    xml,
    /<enclosure url="https:\/\/example\.com\/audio\/day-\d{3}-.+\.mp3" length="\d+" type="audio\/mpeg" \/>/,
  );
  assert.match(xml, /<itunes:episode>35<\/itunes:episode>/);
  assert.match(xml, /Kindle chapter Day 35/);
});
