import { useState } from "react";
import { Link } from "react-router-dom";

import { youtubeVideo } from "../../api";
import { Badge, Segmented, Section } from "../../components/ui";
import { count, percent } from "../../format";
import { useMap } from "./context";

const SOURCE_NAMES: Record<string, string> = {
  SHORTS: "Shorts feed",
  SUBSCRIBER: "Home and subscriptions",
  YT_SEARCH: "YouTube search",
  YT_OTHER_PAGE: "Other YouTube pages",
  RELATED_VIDEO: "Suggested videos",
  YT_CHANNEL: "Your channel page",
  NO_LINK_OTHER: "Direct or unknown",
  PLAYLIST: "Playlists",
  EXT_URL: "Other websites",
  NOTIFICATION: "Notifications",
  END_SCREEN: "End screens",
  HASHTAGS: "Hashtag pages",
  SHORTS_CONTENT_LINKS: "Links in Shorts",
  SOUND_PAGE: "Sound pages",
  IMMERSIVE_LIVE: "Live feed",
};

const VERDICT: Record<string, { word: string; tone: "accent" | "danger" | "plain" }> = {
  holding: { word: "Holding", tone: "accent" },
  dropping: { word: "Dropping", tone: "danger" },
  unknown: { word: "Unknown", tone: "plain" },
};

type Filter = "all" | "holding" | "dropping" | "unknown";

export function OwnTab() {
  const { m } = useMap();
  const own = m.own!;
  const [filter, setFilter] = useState<Filter>("all");
  const verdict = (v: string) => (v in VERDICT ? v : "unknown");
  const rows = own.videos.filter((v) => filter === "all" || verdict(v.verdict) === filter);
  const known = new Set(m.channels.map((c) => c.id));
  const allMinutes = own.sources.reduce((sum, s) => sum + s.minutes, 0) || 1;
  const score = own.accuracy;
  const days = own.windowDays ?? 90;

  return (
    <div className="flex flex-col gap-6">
      <Section title="Traffic sources" hint={`The last ${days} days. Views and watch time can come from different places, so both are shown.`}>
        <ul className="flex flex-col gap-1.5">
          <li className="grid grid-cols-[minmax(120px,190px)_minmax(0,1fr)_90px_90px] gap-3 text-xs text-ink-3">
            <span />
            <span />
            <span className="text-right">Views</span>
            <span className="text-right">Watch time</span>
          </li>
          {own.sources.slice(0, 10).map((s) => (
            <li key={s.source} className="grid grid-cols-[minmax(120px,190px)_minmax(0,1fr)_90px_90px] items-center gap-3 text-sm">
              <span className="truncate text-ink-2">{SOURCE_NAMES[s.source] ?? s.source}</span>
              <span className="h-2 overflow-hidden rounded-full bg-overlay">
                <span className="block h-full rounded-full bg-accent" style={{ width: percent(s.share) }} />
              </span>
              <span className="text-right text-xs text-ink-3">
                {count(s.views)} · {percent(s.share)}
              </span>
              <span className="text-right text-xs text-ink-2">{percent(s.minutes / allMinutes)}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section
        title="Your videos"
        hint={`Retention against your own median${own.medians.retention != null ? ` of ${own.medians.retention}% watched` : ""}.`}
        aside={
          <Segmented<Filter>
            label="Which videos"
            value={filter}
            onChange={setFilter}
            options={[
              { value: "all", label: "All" },
              { value: "holding", label: "Holding" },
              { value: "dropping", label: "Dropping" },
              { value: "unknown", label: "Unknown" },
            ]}
          />
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] table-fixed text-sm">
            <thead className="text-left text-xs text-ink-3">
              <tr>
                <th className="py-1 font-medium">Video</th>
                <th className="w-24 py-1 text-right font-medium">Views</th>
                <th className="w-24 py-1 text-right font-medium">Watched</th>
                <th className="w-32 py-1 pl-4 font-medium">Retention</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((v) => {
                const verdictInfo = VERDICT[verdict(v.verdict)]!;
                return (
                  <tr key={v.id} className="border-t border-line" title={v.note}>
                    <td className="truncate py-1.5 pr-2">
                      <a href={youtubeVideo(v.id)} target="_blank" rel="noreferrer noopener" className="text-ink hover:underline">
                        {v.title}
                      </a>
                    </td>
                    <td className="py-1.5 text-right text-ink-2">{count(v.period_views ?? v.views)}</td>
                    <td className="py-1.5 text-right text-ink-2">{v.avg_view_pct == null ? "?" : `${v.avg_view_pct}%`}</td>
                    <td className="py-1.5 pl-4">
                      <Badge tone={verdictInfo.tone}>{verdictInfo.word}</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {rows.length === 0 && <p className="py-4 text-sm text-ink-3">No videos with this verdict.</p>}
        </div>
      </Section>

      <Section title="Channels that send you viewers" hint="Channels whose videos YouTube suggested yours beside, and viewers clicked.">
        {own.traffic.length === 0 ? (
          <p className="text-sm text-ink-3">No suggested traffic in this window.</p>
        ) : (
          <ul className="grid gap-1 md:grid-cols-2">
            {own.traffic.map((t) => (
              <li key={t.id} className="flex items-center justify-between gap-3 rounded-sm px-2 py-1.5 text-sm hover:bg-overlay">
                {known.has(t.id) ? (
                  <Link to={`/c/${m.id}?channel=${encodeURIComponent(t.id)}`} className="truncate text-ink hover:underline">
                    {t.title}
                  </Link>
                ) : (
                  <span className="truncate text-ink-2">{t.title}</span>
                )}
                <span className="shrink-0 text-xs text-busy">{count(t.views)} views</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {score && (
        <Section title="Accuracy of the public map" hint="How much of your real Suggested traffic the public map found by itself.">
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {(
              [
                ["Channels sending viewers", count(score.real)],
                ["Found by the map", `${count(score.found)} of ${count(score.real)}`],
                ["Found as near", count(score.near)],
                ["Views covered", percent(score.views_found / (score.views_named || 1))],
              ] as [string, string][]
            ).map(([k, v]) => (
              <div key={k} className="rounded-md bg-overlay px-3 py-2.5">
                <dt className="text-xs text-ink-3">{k}</dt>
                <dd className="text-lg font-semibold text-ink">{v}</dd>
              </div>
            ))}
          </dl>
          {score.views_suggested != null && (
            <p className="mt-3 text-xs text-ink-3">
              YouTube names the source of {count(score.views_named)} of your {count(score.views_suggested)} Suggested views, so the score covers that part.
            </p>
          )}
        </Section>
      )}
    </div>
  );
}
