import {
  copyFile,
  mkdir,
  readFile,
  readdir,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const docsRoot = path.join(siteRoot, "docs");
const baseUrl = (
  process.env.PUBLIC_BASE_URL ||
  "https://bel9777.github.io/ai-foundations-daily-audio/"
).replace(/\/?$/, "/");
const mediaBaseUrl = (
  process.env.PUBLIC_MEDIA_BASE_URL ||
  "https://cdn.jsdelivr.net/gh/bel9777/ai-foundations-daily-audio@main/docs/"
).replace(/\/?$/, "/");
const episodes = JSON.parse(
  await readFile(path.join(siteRoot, "data", "episodes.json"), "utf8"),
);

function html(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function xml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function absolute(relativePath) {
  return new URL(relativePath.replace(/^\//, ""), baseUrl).href;
}

function mediaAbsolute(relativePath) {
  return new URL(relativePath.replace(/^\//, ""), mediaBaseUrl).href;
}

function publishedAudioName(episode) {
  const sourceName = path.basename(episode.audioPath, ".mp3");
  return `${sourceName}-${episode.audioBytes}.mp3`;
}

function publishedTranscriptName(episode) {
  const sourceName = path.basename(episode.transcriptPath, ".txt");
  return `${sourceName}-${episode.audioBytes}.txt`;
}

function publishedAudioPath(episode) {
  return `audio/${publishedAudioName(episode)}`;
}

function publishedTranscriptPath(episode) {
  return `transcripts/${publishedTranscriptName(episode)}`;
}

function displayDate(isoDate) {
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "America/New_York",
  }).format(new Date(isoDate));
}

await rm(docsRoot, { recursive: true, force: true });
await Promise.all([
  mkdir(path.join(docsRoot, "audio"), { recursive: true }),
  mkdir(path.join(docsRoot, "transcripts"), { recursive: true }),
]);

await copyFile(
  path.join(siteRoot, "public", "podcast-cover.png"),
  path.join(docsRoot, "podcast-cover.png"),
);

for (const episode of episodes) {
  const audioName = path.basename(episode.audioPath);
  const transcriptName = path.basename(episode.transcriptPath);
  const publicAudioName = publishedAudioName(episode);
  const publicTranscriptName = publishedTranscriptName(episode);
  await Promise.all([
    copyFile(
      path.join(siteRoot, "public", "audio", audioName),
      path.join(docsRoot, "audio", publicAudioName),
    ),
    copyFile(
      path.join(siteRoot, "public", "transcripts", transcriptName),
      path.join(docsRoot, "transcripts", publicTranscriptName),
    ),
  ]);

  const copiedAudio = await stat(path.join(docsRoot, "audio", publicAudioName));
  if (copiedAudio.size !== episode.audioBytes) {
    throw new Error(`Audio length changed while copying ${audioName}.`);
  }
}

const newest = episodes[0];
const archiveCards = episodes
  .map(
    (episode) => `
          <article class="episode-card" id="day-${String(episode.day).padStart(3, "0")}">
            <div class="card-day">DAY ${String(episode.day).padStart(2, "0")}</div>
            <div class="card-main">
              <div class="episode-meta">
                <span>${html(displayDate(episode.publishedAt))}</span>
                <span>${html(episode.durationLabel)}</span>
              </div>
              <h3>${html(episode.title)}</h3>
              <p>Matches the “${html(episode.subject)}” email and Kindle chapter Day ${episode.day}.</p>
            </div>
            <audio controls preload="none" src="${html(publishedAudioPath(episode))}">
              <a href="${html(publishedAudioPath(episode))}">Download</a>
            </audio>
          </article>`,
  )
  .join("");

const latestMarkup = newest
  ? `
      <section class="latest section-shell" aria-labelledby="latest-title">
        <div class="section-label">Latest episode</div>
        <article class="latest-card">
          <div class="episode-number">
            <span>Day</span>
            ${String(newest.day).padStart(2, "0")}
          </div>
          <div class="latest-body">
            <div class="episode-meta">
              <span>${html(displayDate(newest.publishedAt))}</span>
              <span>${html(newest.durationLabel)}</span>
            </div>
            <h2 id="latest-title">${html(newest.title)}</h2>
            <p>${html(newest.summary)}</p>
            <audio controls preload="metadata" src="${html(publishedAudioPath(newest))}">
              <a href="${html(publishedAudioPath(newest))}">Download this episode</a>
            </audio>
            <div class="format-row" aria-label="Matching course formats">
              <span>Same lesson</span>
              <strong>Daily email</strong>
              <span aria-hidden="true">→</span>
              <strong>Kindle Day ${newest.day}</strong>
              <span aria-hidden="true">→</span>
              <strong>Episode ${newest.day}</strong>
            </div>
          </div>
        </article>
      </section>`
  : "";

const page = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex, nofollow, noarchive">
    <title>AI Foundations — Daily Audio Course</title>
    <meta name="description" content="Every episode is the audio companion to the matching AI Foundations email and Kindle chapter.">
    <meta property="og:title" content="AI Foundations — Daily Audio Course">
    <meta property="og:description" content="Listen to the same daily lesson from the email course and Kindle library.">
    <meta property="og:image" content="${html(absolute("podcast-cover.png"))}">
    <link rel="icon" href="podcast-cover.png">
    <link rel="alternate" type="application/rss+xml" title="AI Foundations Daily Audio" href="feed.rss">
    <link rel="stylesheet" href="styles.css">
  </head>
  <body>
    <main>
      <section class="hero">
        <nav class="nav-shell" aria-label="Main navigation">
          <a class="wordmark" href="./">AI <span>FOUNDATIONS</span></a>
          <a class="feed-link" href="feed.rss">RSS feed</a>
        </nav>

        <div class="hero-grid">
          <div class="hero-copy">
            <div class="eyebrow">Email ↔ Kindle ↔ Podcast</div>
            <h1>Your daily AI course, ready when your ears are.</h1>
            <p class="lede">Every episode is built from the same source lesson as that day’s course email and Kindle chapter. Listen here or add the unlisted feed to Apple Podcasts.</p>
            <div class="feed-controls">
              <a class="primary-button" href="#latest-title">Play the latest episode</a>
              <button class="secondary-button" id="copy-feed" type="button">Copy Apple Podcasts feed</button>
            </div>
            <p class="privacy-note">Public by URL • no paid app required • not submitted to a podcast directory</p>
          </div>

          <div class="cover-wrap">
            <div class="cover-glow" aria-hidden="true"></div>
            <img class="cover" src="podcast-cover.png" alt="AI Foundations Daily Audio Course cover" width="1400" height="1400">
          </div>
        </div>
      </section>

      ${latestMarkup}

      <section class="archive section-shell" aria-labelledby="archive-title">
        <div class="archive-heading">
          <div>
            <div class="section-label">Course archive</div>
            <h2 id="archive-title">Listen in any order</h2>
          </div>
          <p>New lessons appear automatically. Earlier lessons are being backfilled into audio.</p>
        </div>
        <div class="episode-list">${archiveCards}</div>
      </section>

      <section class="how-it-works">
        <div class="section-shell">
          <div class="section-label">One lesson, three formats</div>
          <h2>Pick up the course wherever you left off.</h2>
          <div class="format-grid">
            <article><span>01</span><h3>Read the email</h3><p>The daily lesson lands first with the complete course material.</p></article>
            <article><span>02</span><h3>Keep the chapter</h3><p>The same source is added to the expanding Kindle library.</p></article>
            <article><span>03</span><h3>Listen anywhere</h3><p>The matching day and title become a chaptered audio episode.</p></article>
          </div>
        </div>
      </section>

      <footer class="section-shell">
        <p>AI Foundations • Personal daily course library</p>
        <a href="feed.rss">RSS feed</a>
      </footer>
    </main>
    <script>
      const copyButton = document.getElementById("copy-feed");
      copyButton.addEventListener("click", async () => {
        await navigator.clipboard.writeText(new URL("feed.rss", window.location.href).href);
        copyButton.textContent = "Feed URL copied";
        window.setTimeout(() => {
          copyButton.textContent = "Copy Apple Podcasts feed";
        }, 2200);
      });
    </script>
  </body>
</html>
`;

const items = episodes
  .map((episode) => {
    const episodeUrl = `${baseUrl}#day-${String(episode.day).padStart(3, "0")}`;
    const audioUrl = mediaAbsolute(publishedAudioPath(episode));
    const transcriptUrl = mediaAbsolute(publishedTranscriptPath(episode));
    const description = `The audio companion to ${episode.subject} and Kindle chapter Day ${episode.day}. ${episode.summary}`;

    return `    <item>
      <title>${xml(`Day ${episode.day}: ${episode.title}`)}</title>
      <link>${xml(episodeUrl)}</link>
      <guid isPermaLink="false">${xml(`urn:ai-foundations:gmail:${episode.sourceMessageId}`)}</guid>
      <pubDate>${xml(new Date(episode.publishedAt).toUTCString())}</pubDate>
      <description>${xml(description)}</description>
      <itunes:title>${xml(episode.title)}</itunes:title>
      <itunes:episode>${episode.day}</itunes:episode>
      <itunes:season>1</itunes:season>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:duration>${xml(episode.durationLabel)}</itunes:duration>
      <itunes:summary>${xml(description)}</itunes:summary>
      <itunes:explicit>false</itunes:explicit>
      <enclosure url="${xml(audioUrl)}" length="${episode.audioBytes}" type="audio/mpeg" />
      <podcast:transcript url="${xml(transcriptUrl)}" type="text/plain" rel="captions" />
    </item>`;
  })
  .join("\n");

const feed = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
  xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>AI Foundations — Daily Audio Course</title>
    <link>${xml(baseUrl)}</link>
    <atom:link href="${xml(absolute("feed.rss"))}" rel="self" type="application/rss+xml" />
    <description>Short daily AI lessons connected to the AI Foundations email course and Kindle library.</description>
    <language>en-us</language>
    <lastBuildDate>${xml(new Date(newest?.publishedAt || Date.now()).toUTCString())}</lastBuildDate>
    <generator>AI Foundations Library Builder</generator>
    <itunes:author>AI Foundations</itunes:author>
    <itunes:summary>Every episode is the audio companion to the matching daily course email and Kindle chapter.</itunes:summary>
    <itunes:type>serial</itunes:type>
    <itunes:explicit>false</itunes:explicit>
    <itunes:image href="${xml(absolute("podcast-cover.png"))}" />
    <itunes:category text="Education">
      <itunes:category text="Courses" />
    </itunes:category>
${items}
  </channel>
</rss>
`;

const css = (
  await readFile(path.join(siteRoot, "app", "globals.css"), "utf8")
).replace('@import "tailwindcss";', "");

await Promise.all([
  writeFile(path.join(docsRoot, "index.html"), page, "utf8"),
  writeFile(path.join(docsRoot, "404.html"), page, "utf8"),
  writeFile(path.join(docsRoot, "styles.css"), css, "utf8"),
  writeFile(path.join(docsRoot, "feed.xml"), feed, "utf8"),
  writeFile(path.join(docsRoot, "feed.rss"), feed, "utf8"),
  writeFile(
    path.join(docsRoot, "robots.txt"),
    "User-agent: *\nDisallow: /\n",
    "utf8",
  ),
  writeFile(path.join(docsRoot, ".nojekyll"), "", "utf8"),
]);

const builtFiles = await readdir(docsRoot);
console.log(
  `Built GitHub Pages site with ${episodes.length} episode(s): ${builtFiles.join(", ")}`,
);
