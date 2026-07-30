import episodeData from "@/data/episodes.json";

type Episode = {
  day: number;
  title: string;
  subject: string;
  publishedAt: string;
  sourceMessageId: string;
  audioPath: string;
  transcriptPath: string;
  audioBytes: number;
  durationSeconds: number;
  durationLabel: string;
  summary: string;
};

const episodes = episodeData as Episode[];

function xml(value: string | number) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

export async function GET(request: Request) {
  const origin = new URL(request.url).origin;
  const feedUrl = `${origin}/feed.xml`;
  const imageUrl = `${origin}/podcast-cover.png`;
  const latestDate = episodes[0]?.publishedAt ?? new Date().toISOString();

  const items = episodes
    .map((episode) => {
      const episodeUrl = `${origin}/#day-${String(episode.day).padStart(3, "0")}`;
      const audioUrl = `${origin}${episode.audioPath}`;
      const transcriptUrl = `${origin}${episode.transcriptPath}`;
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

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
  xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>AI Foundations — Daily Audio Course</title>
    <link>${xml(origin)}</link>
    <atom:link href="${xml(feedUrl)}" rel="self" type="application/rss+xml" />
    <description>Short daily AI lessons connected to the AI Foundations email course and Kindle library.</description>
    <language>en-us</language>
    <lastBuildDate>${xml(new Date(latestDate).toUTCString())}</lastBuildDate>
    <generator>AI Foundations Library Builder</generator>
    <itunes:author>AI Foundations</itunes:author>
    <itunes:summary>Every episode is the audio companion to the matching daily course email and Kindle chapter.</itunes:summary>
    <itunes:type>serial</itunes:type>
    <itunes:explicit>false</itunes:explicit>
    <itunes:image href="${xml(imageUrl)}" />
    <itunes:category text="Education">
      <itunes:category text="Courses" />
    </itunes:category>
${items}
  </channel>
</rss>`;

  return new Response(body, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=300, s-maxage=300",
    },
  });
}
