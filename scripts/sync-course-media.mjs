import { execFileSync } from "node:child_process";
import {
  copyFile,
  mkdir,
  readFile,
  readdir,
  stat,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = path.resolve(siteRoot, "..", "..");
const lessonDir = path.join(
  projectRoot,
  "work",
  "ai-foundations-library",
  "lessons",
);
const podcastDir = path.join(
  projectRoot,
  "outputs",
  "AI-Foundations-Library",
  "podcast",
);
const publicAudioDir = path.join(siteRoot, "public", "audio");
const publicTranscriptDir = path.join(siteRoot, "public", "transcripts");
const dataDir = path.join(siteRoot, "data");

await Promise.all([
  mkdir(publicAudioDir, { recursive: true }),
  mkdir(publicTranscriptDir, { recursive: true }),
  mkdir(dataDir, { recursive: true }),
]);

const audioFiles = (await readdir(podcastDir))
  .filter((name) => /^day-\d{3}-[a-z0-9-]+\.mp3$/i.test(name))
  .sort();

function durationFor(filePath) {
  try {
    const output = execFileSync(
      "ffprobe",
      [
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        filePath,
      ],
      { encoding: "utf8" },
    );
    return Math.max(1, Math.round(Number.parseFloat(output)));
  } catch {
    return 0;
  }
}

function durationLabel(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remaining = seconds % 60;
  const values =
    hours > 0 ? [hours, minutes, remaining] : [minutes, remaining];
  return values.map((value) => String(value).padStart(2, "0")).join(":");
}

function cleanText(value) {
  return value
    .replace(/<[^>]+>/g, " ")
    .replace(/[#*_`|]+/g, " ")
    .replace(/\s+/g, " ")
    .replaceAll("\u00e2\u20ac\u2122", "\u2019")
    .replaceAll("\u00e2\u20ac\u0153", "\u201c")
    .replaceAll("\u00e2\u20ac\u009d", "\u201d")
    .replaceAll("\u00e2\u20ac\u201d", "\u2014")
    .replaceAll("\u00e2\u20ac\u201c", "\u2013")
    .replaceAll("\u00e2\u20ac\u00a6", "\u2026")
    .trim();
}

function shortSummary(lesson) {
  const text = cleanText(lesson.plain || lesson.html || "");
  const objectiveMatch = text.match(
    /\bObjective\b[:\s]*(.{80,440}?)(?=\s+\b(?:Prerequisites|Why this matters|Today.s Big Idea)\b)/i,
  );
  const source = objectiveMatch?.[1] || text;
  return source.length > 300 ? `${source.slice(0, 297).trimEnd()}…` : source;
}

const episodes = [];

for (const audioName of audioFiles) {
  const day = Number.parseInt(audioName.slice(4, 7), 10);
  const lessonPath = path.join(
    lessonDir,
    `day-${String(day).padStart(3, "0")}.json`,
  );
  const lesson = JSON.parse(await readFile(lessonPath, "utf8"));
  const sourceAudio = path.join(podcastDir, audioName);
  const targetAudio = path.join(publicAudioDir, audioName);
  await copyFile(sourceAudio, targetAudio);

  const transcriptName = `day-${String(day).padStart(3, "0")}.txt`;
  const audioTranscript = Array.isArray(lesson.audio_segments)
    ? lesson.audio_segments
        .map((segment) => `${segment.title}\n\n${segment.text}`)
        .join("\n\n")
    : cleanText(lesson.plain || lesson.html || "");
  await writeFile(
    path.join(publicTranscriptDir, transcriptName),
    `AI Foundations — Day ${day}: ${lesson.title}\n\n${audioTranscript}\n`,
    "utf8",
  );

  const audioStats = await stat(targetAudio);
  const seconds = durationFor(targetAudio);

  episodes.push({
    day,
    title: lesson.title,
    subject: lesson.subject,
    publishedAt: lesson.date,
    sourceMessageId: lesson.source_message_id,
    audioPath: `/audio/${audioName}`,
    transcriptPath: `/transcripts/${transcriptName}`,
    audioBytes: audioStats.size,
    durationSeconds: seconds,
    durationLabel: durationLabel(seconds),
    summary: shortSummary(lesson),
  });
}

episodes.sort((a, b) => b.day - a.day);
await writeFile(
  path.join(dataDir, "episodes.json"),
  `${JSON.stringify(episodes, null, 2)}\n`,
  "utf8",
);

console.log(`Synced ${episodes.length} podcast episode(s).`);
