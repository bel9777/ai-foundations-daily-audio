import type { Metadata } from "next";
import Image from "next/image";
import episodeData from "@/data/episodes.json";
import { FeedControls } from "./components/FeedControls";

export const metadata: Metadata = {
  title: "Daily Audio Course",
  description:
    "Every episode is the audio companion to the matching AI Foundations email and Kindle chapter.",
};

type Episode = {
  day: number;
  title: string;
  subject: string;
  publishedAt: string;
  audioPath: string;
  durationLabel: string;
  summary: string;
};

const episodes = episodeData as Episode[];
const newest = episodes[0];

function displayDate(isoDate: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "America/New_York",
  }).format(new Date(isoDate));
}

export default function Home() {
  return (
    <main>
      <section className="hero">
        <nav className="nav-shell" aria-label="Main navigation">
          <a className="wordmark" href="#">
            AI <span>FOUNDATIONS</span>
          </a>
          <a className="feed-link" href="/feed.xml">
            RSS feed
          </a>
        </nav>

        <div className="hero-grid">
          <div className="hero-copy">
            <div className="eyebrow">Email ↔ Kindle ↔ Podcast</div>
            <h1>Your daily AI course, ready when your ears are.</h1>
            <p className="lede">
              Every episode is built from the same source lesson as that
              day&apos;s course email and Kindle chapter. Listen here or add the
              unlisted feed to Apple Podcasts.
            </p>
            <FeedControls />
            <p className="privacy-note">
              Unlisted feed • no paid app required • not submitted to a public
              podcast directory
            </p>
          </div>

          <div className="cover-wrap">
            <div className="cover-glow" aria-hidden="true" />
            <Image
              className="cover"
              src="/podcast-cover.png"
              alt="AI Foundations Daily Audio Course cover"
              width="1400"
              height="1400"
              priority
              unoptimized
            />
          </div>
        </div>
      </section>

      {newest ? (
        <section className="latest section-shell" aria-labelledby="latest-title">
          <div className="section-label">Latest episode</div>
          <article
            className="latest-card"
            id={`day-${String(newest.day).padStart(3, "0")}`}
          >
            <div className="episode-number">
              <span>Day</span>
              {String(newest.day).padStart(2, "0")}
            </div>
            <div className="latest-body">
              <div className="episode-meta">
                <span>{displayDate(newest.publishedAt)}</span>
                <span>{newest.durationLabel}</span>
              </div>
              <h2 id="latest-title">{newest.title}</h2>
              <p>{newest.summary}</p>
              <audio controls preload="metadata" src={newest.audioPath}>
                <a href={newest.audioPath}>Download this episode</a>
              </audio>
              <div className="format-row" aria-label="Matching course formats">
                <span>Same lesson</span>
                <strong>Daily email</strong>
                <span aria-hidden="true">→</span>
                <strong>Kindle Day {newest.day}</strong>
                <span aria-hidden="true">→</span>
                <strong>Episode {newest.day}</strong>
              </div>
            </div>
          </article>
        </section>
      ) : null}

      <section className="archive section-shell" aria-labelledby="archive-title">
        <div className="archive-heading">
          <div>
            <div className="section-label">Course archive</div>
            <h2 id="archive-title">Listen in any order</h2>
          </div>
          <p>
            New lessons appear automatically. Earlier lessons are being
            backfilled into audio.
          </p>
        </div>

        <div className="episode-list">
          {episodes.map((episode) => (
            <article
              className="episode-card"
              id={`day-${String(episode.day).padStart(3, "0")}`}
              key={episode.day}
            >
              <div className="card-day">
                DAY {String(episode.day).padStart(2, "0")}
              </div>
              <div className="card-main">
                <div className="episode-meta">
                  <span>{displayDate(episode.publishedAt)}</span>
                  <span>{episode.durationLabel}</span>
                </div>
                <h3>{episode.title}</h3>
                <p>
                  Matches the “{episode.subject}” email and Kindle chapter Day{" "}
                  {episode.day}.
                </p>
              </div>
              <audio controls preload="none" src={episode.audioPath}>
                <a href={episode.audioPath}>Download</a>
              </audio>
            </article>
          ))}
        </div>
      </section>

      <section className="how-it-works">
        <div className="section-shell">
          <div className="section-label">One lesson, three formats</div>
          <h2>Pick up the course wherever you left off.</h2>
          <div className="format-grid">
            <article>
              <span>01</span>
              <h3>Read the email</h3>
              <p>
                The daily lesson lands first with the complete course material.
              </p>
            </article>
            <article>
              <span>02</span>
              <h3>Keep the chapter</h3>
              <p>The same source is added to the expanding Kindle library.</p>
            </article>
            <article>
              <span>03</span>
              <h3>Listen anywhere</h3>
              <p>
                The matching day and title become a chaptered audio episode.
              </p>
            </article>
          </div>
        </div>
      </section>

      <footer className="section-shell">
        <p>AI Foundations • Personal daily course library</p>
        <a href="/feed.xml">RSS feed</a>
      </footer>
    </main>
  );
}
