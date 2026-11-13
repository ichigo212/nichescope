import type { ReactNode } from "react";

import { youtubeVideo } from "../api";

export type VideoLookup = Map<string, { title: string }>;

/** An answer saved as one long paragraph: break it where its own structure already is. */
function unflatten(text: string): string {
  if (text.includes("\n")) return text;
  return text
    .replace(/ {2,}/g, "\n\n")
    .replace(/([.:)!?\]]) +- +(?=\S)/g, "$1\n- ")
    .replace(/([.:)!?\]]) +(\d{1,2}\. +[A-Z])/g, "$1\n\n$2");
}

/** **bold**, `code` and known video ids, as elements. Never innerHTML. */
function Inline({ text, videos }: { text: string; videos: VideoLookup }) {
  const out: ReactNode[] = [];
  const re = /\*\*([^*]+)\*\*|`([^`]+)`|(?<![\w-])([\w-]{11})(?![\w-])/g;
  let at = 0;
  let key = 0;
  for (let m = re.exec(text); m; m = re.exec(text)) {
    if (m[3] && !videos.has(m[3])) continue;
    out.push(text.slice(at, m.index));
    const id = m[3] ?? (m[2] && videos.has(m[2]) ? m[2] : null);
    if (id) {
      out.push(
        <a key={key++} href={youtubeVideo(id)} target="_blank" rel="noreferrer noopener" className="text-accent underline-offset-2 hover:underline" title={videos.get(id)?.title}>
          watch
        </a>,
      );
    } else if (m[1]) {
      out.push(
        <strong key={key++} className="font-semibold text-ink">
          {m[1]}
        </strong>,
      );
    } else {
      out.push(
        <code key={key++} className="rounded-[4px] bg-overlay px-1 py-px font-mono text-[0.9em] text-accent">
          {m[2]}
        </code>,
      );
    }
    at = m.index + m[0].length;
  }
  out.push(text.slice(at));
  return <>{out}</>;
}

/** The small Markdown the model writes: headings, lists and paragraphs. */
export function Markdown({ text, videos = new Map(), className = "" }: { text: string; videos?: VideoLookup; className?: string }) {
  const blocks: ReactNode[] = [];
  let items: { ordered: boolean; text: string; depth: number }[] = [];
  const flush = () => {
    if (!items.length) return;
    const ordered = items[0]!.ordered;
    const Tag = ordered ? "ol" : "ul";
    blocks.push(
      <Tag key={blocks.length} className={(ordered ? "list-decimal" : "list-disc") + " flex flex-col gap-1.5 pl-5 marker:text-ink-3"}>
        {items.map((it, i) => (
          <li key={i} className={it.depth ? "ml-4" : undefined}>
            <Inline text={it.text} videos={videos} />
          </li>
        ))}
      </Tag>,
    );
    items = [];
  };
  for (const raw of unflatten(text).split("\n")) {
    const line = raw.trimEnd();
    const head = /^(#{1,4})\s+(.*)$/.exec(line.trim());
    const item = /^(\s*)([-*•]|\d{1,2}[.)])\s+(.*)$/.exec(line);
    if (head) {
      flush();
      blocks.push(
        <h4 key={blocks.length} className="mt-2 text-sm font-semibold text-ink first:mt-0">
          <Inline text={head[2]!} videos={videos} />
        </h4>,
      );
    } else if (item) {
      const ordered = /\d/.test(item[2]!);
      if (items.length && items[0]!.ordered !== ordered) flush();
      items.push({ ordered, text: item[3]!, depth: item[1]!.length >= 2 ? 1 : 0 });
    } else if (!line.trim()) {
      flush();
    } else {
      flush();
      blocks.push(
        <p key={blocks.length}>
          <Inline text={line.trim()} videos={videos} />
        </p>,
      );
    }
  }
  flush();
  return <div className={"flex max-w-[78ch] flex-col gap-2.5 text-[14px] leading-relaxed text-ink-2 " + className}>{blocks}</div>;
}
