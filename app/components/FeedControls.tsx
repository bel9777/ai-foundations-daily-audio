"use client";

import { useState } from "react";

export function FeedControls() {
  const [copied, setCopied] = useState(false);

  async function copyFeed() {
    const feedUrl = `${window.location.origin}/feed.xml`;
    await navigator.clipboard.writeText(feedUrl);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2200);
  }

  return (
    <div className="feed-controls">
      <a className="primary-button" href="#latest-title">
        Play the latest episode
      </a>
      <button className="secondary-button" type="button" onClick={copyFeed}>
        {copied ? "Feed URL copied" : "Copy Apple Podcasts feed"}
      </button>
    </div>
  );
}
