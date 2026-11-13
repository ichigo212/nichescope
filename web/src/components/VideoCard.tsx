import type { ReactNode } from "react";

import { youtubeVideo } from "../api";
import { ago, count, duration, times } from "../format";

export interface CardVideo {
  id: string;
  title: string;
  views: number | null;
  published_at?: string;
  thumbnail: string;
  seconds?: number | null;
  outlier: number | null;
  channel?: string;
}

export function OutlierBadge({ x, title = "Its views over its channel's usual" }: { x: number; title?: string }) {
  return (
    <span className={"shrink-0 rounded-[4px] px-1.5 font-bold " + (x >= 1 ? "bg-busy/15 text-busy" : "bg-danger/15 text-danger")} title={title}>
      {times(x)}
    </span>
  );
}

/** A video as a thumbnail card. Opens on YouTube. */
export function VideoCard({ v, sub }: { v: CardVideo; sub?: ReactNode }) {
  return (
    <a
      href={youtubeVideo(v.id)}
      target="_blank"
      rel="noreferrer noopener"
      className="group flex min-w-0 flex-col gap-1.5 rounded-sm text-left outline-none focus-visible:ring-2 focus-visible:ring-accent"
    >
      <span className="relative block aspect-video w-full overflow-hidden rounded-md bg-overlay">
        {v.thumbnail && (
          <img
            src={v.thumbnail}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
            className="size-full object-cover transition-transform duration-200 group-hover:scale-[1.03]"
          />
        )}
        {!!v.seconds && v.seconds > 0 && (
          <span className="absolute right-1.5 bottom-1.5 rounded-[4px] bg-black/80 px-1.5 text-xs font-semibold text-white">{duration(v.seconds)}</span>
        )}
      </span>
      <span className="flex min-w-0 items-center gap-2 text-xs text-ink-3">
        {v.outlier != null && <OutlierBadge x={v.outlier} />}
        <span className="truncate">
          {v.views == null ? "views hidden" : `${count(v.views)} views`}
          {v.published_at ? ` · ${ago(v.published_at)}` : ""}
        </span>
      </span>
      <span className="line-clamp-2 text-[13px] leading-snug font-medium text-ink">{v.title}</span>
      {v.channel && <span className="truncate text-xs text-ink-3">{v.channel}</span>}
      {sub}
    </a>
  );
}

/** A row of small video links, for evidence under a topic. */
export function VideoChip({ v }: { v: CardVideo }) {
  return (
    <a
      href={youtubeVideo(v.id)}
      target="_blank"
      rel="noreferrer noopener"
      title={v.title}
      className="flex max-w-[280px] min-w-0 items-center gap-2 rounded-sm border border-line bg-overlay p-1 pr-2.5 hover:border-line-strong"
    >
      {v.thumbnail ? (
        <img src={v.thumbnail} alt="" loading="lazy" referrerPolicy="no-referrer" className="aspect-video w-16 shrink-0 rounded-[4px] object-cover" />
      ) : (
        <span className="aspect-video w-16 shrink-0 rounded-[4px] bg-raised" />
      )}
      <span className="min-w-0">
        <span className="block truncate text-xs font-medium text-ink">{v.title}</span>
        <span className="flex items-center gap-1.5 text-[11px] text-ink-3">
          {v.outlier != null && <span className="font-bold text-busy">{times(v.outlier)}</span>}
          <span className="truncate">
            {count(v.views)} views{v.channel ? ` · ${v.channel}` : ""}
          </span>
        </span>
      </span>
    </a>
  );
}
