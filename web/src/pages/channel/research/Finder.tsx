import { Search } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { findChannels, findVideos, youtubeChannel, youtubeVideo, type Filters } from "../../../api";
import { Avatar, Button, Empty, Field, Input, Segmented, Select, Switch } from "../../../components/ui";
import { VideoCard } from "../../../components/VideoCard";
import { count, startedAgo, times } from "../../../format";
import { attempt } from "../../../toasts";
import type { FoundChannel, FoundVideo, StoreStats } from "../../../types";
import { useMap } from "../context";

type Fields = Record<string, string>;
const PAGE = 24;

const VIDEO_PRESETS: { label: string; hint: string; fields: Fields }[] = [
  { label: "Breaking out this month", hint: "Published in the last 30 days, at least 3× its channel's usual", fields: { published_within_days: "30", outlier_min: "3", sort: "outlier" } },
  { label: "Small channels, big videos", hint: "Channels under 10K subscribers with a video at 5× or more", fields: { channel_subscribers_max: "10000", outlier_min: "5", published_within_days: "90", sort: "outlier" } },
  { label: "Fastest right now", hint: "Most views a day among videos from the last two weeks", fields: { published_within_days: "14", sort: "per_day" } },
  { label: "Flops to avoid", hint: "At least a week old and under a third of its channel's usual", fields: { outlier_max: "0.3", published_within_days: "90", sort: "flops" } },
];

const CHANNEL_PRESETS: { label: string; hint: string; fields: Fields }[] = [
  { label: "New channels already getting views", hint: "Started in the last 6 months, 50K views or more in 30 days", fields: { started_within_days: "180", views_30d_min: "50000", sort: "views_30d" } },
  { label: "Small but breaking out", hint: "Under 5K subscribers with a video at 5× or more this month", fields: { subscribers_max: "5000", breakout_min: "5", sort: "breakout" } },
  { label: "Biggest in the niche", hint: "Most views in the last 30 days", fields: { sort: "views_30d" } },
];

const VIDEO_FIELDS: [string, string, string][] = [
  ["meaning", "About (searched by meaning)", "a beginner builds a cabin alone"],
  ["title_pattern", "Title matches (* is any text)", "I * for 100 days*"],
  ["words_any", "Title has any of", "challenge, survival"],
  ["description_words", "Title or description has any of", "tutorial, guide"],
  ["published_within_days", "Published in the last (days)", "30"],
  ["views_min", "Views at least", "10000"],
  ["outlier_min", "At least × usual", "3"],
  ["outlier_max", "At most × usual", "0.3"],
  ["minutes_min", "Minutes at least", "20"],
  ["minutes_max", "Minutes at most", "120"],
  ["channel_subscribers_max", "Channel subscribers at most", "10000"],
  ["language", "Language", "en"],
];

const CHANNEL_FIELDS: [string, string, string][] = [
  ["title_pattern", "Video titles match (* is any text)", "*full guide*"],
  ["name_regex", "Name has", "kitchen|cooking"],
  ["started_within_days", "Started in the last (days)", "180"],
  ["subscribers_min", "Subscribers at least", "1000"],
  ["subscribers_max", "Subscribers at most", "50000"],
  ["views_30d_min", "Views in 30 days at least", "50000"],
  ["usual_views_min", "Usual video at least", "5000"],
  ["usual_minutes_min", "Average length at least (min)", "20"],
  ["usual_minutes_max", "Average length at most (min)", "90"],
  ["breakout_min", "A video at least × usual", "5"],
  ["bio_regex", "Bio has", "business|contact"],
  ["language", "Language", "en"],
  ["country", "Country", "US"],
];

const VIDEO_SORTS: [string, string][] = [
  ["outlier", "Biggest over usual"],
  ["views", "Most views"],
  ["per_day", "Most views a day"],
  ["newest", "Newest"],
  ["flops", "Furthest under usual"],
];

const CHANNEL_SORTS: [string, string][] = [
  ["views_30d", "Views in 30 days"],
  ["breakout", "Biggest breakout"],
  ["newest", "Newest channel"],
  ["subscribers", "Subscribers"],
  ["usual", "Usual video"],
  ["matches", "Most matching titles"],
];

export function Finder({ kind, onStats }: { kind: "videos" | "channels"; onStats: (s: StoreStats) => void }) {
  const { m } = useMap();
  const presets = kind === "videos" ? VIDEO_PRESETS : CHANNEL_PRESETS;
  const [fields, setFields] = useState<Fields>(presets[0]!.fields);
  const [here, setHere] = useState(true);
  const [grade, setGrade] = useState("any");
  const [steps, setSteps] = useState("");
  const [videos, setVideos] = useState<FoundVideo[]>([]);
  const [channels, setChannels] = useState<FoundChannel[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [more, setMore] = useState(false);
  const [looking, setLooking] = useState(false);
  const set = (k: string, v: string) => setFields((f) => ({ ...f, [k]: v }));

  const find = useCallback(
    async (f: Fields, offset: number) => {
      setLooking(true);
      const scope: Filters = here ? { near: m.id, grade, ...(kind === "channels" && steps ? { near_steps: steps } : {}) } : {};
      const args: Filters = { ...f, ...scope, limit: PAGE, offset };
      if (kind === "videos") {
        const r = await attempt(findVideos(args));
        if (r) {
          setVideos((old) => (offset ? [...old, ...r.videos] : r.videos));
          setTotal(r.total);
          setMore(r.more);
          onStats(r.stats);
        }
      } else {
        const r = await attempt(findChannels(args));
        if (r) {
          setChannels((old) => (offset ? [...old, ...r.channels] : r.channels));
          setTotal(r.total);
          setMore(r.more);
          onStats(r.stats);
        }
      }
      setLooking(false);
    },
    [here, grade, steps, kind, m.id, onStats],
  );

  const latest = useRef(fields);
  latest.current = fields;
  // Search as the view opens, and again whenever the scope changes.
  useEffect(() => {
    void find(latest.current, 0);
  }, [find]);

  const meaning = !!fields.meaning?.trim();
  const sorts = kind === "videos" ? (meaning ? [["meaning", "Closest in meaning"] as [string, string], ...VIDEO_SORTS] : VIDEO_SORTS) : here ? [...CHANNEL_SORTS, ["closest", "Closest to this channel"] as [string, string]] : CHANNEL_SORTS;
  const sort = fields.sort && sorts.some(([v]) => v === fields.sort) ? fields.sort : sorts[0]![0];
  const shown = kind === "videos" ? videos.length : channels.length;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-2">
        {presets.map((p) => (
          <Button
            key={p.label}
            title={p.hint}
            onClick={() => {
              setFields(p.fields);
              void find(p.fields, 0);
            }}
          >
            {p.label}
          </Button>
        ))}
      </div>
      <form
        className="flex flex-col gap-4 rounded-lg border border-line bg-raised p-4"
        onSubmit={(e) => {
          e.preventDefault();
          void find({ ...fields, sort }, 0);
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {(kind === "videos" ? VIDEO_FIELDS : CHANNEL_FIELDS).map(([name, label, hint]) => (
            <Field key={name} label={label}>
              <Input value={fields[name] ?? ""} placeholder={hint} onChange={(e) => set(name, e.target.value)} />
            </Field>
          ))}
          <Field label="Order by">
            <Select label="Order by" value={sort} options={sorts} onChange={(v) => set("sort", v)} />
          </Field>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <Button type="submit" tone="primary" disabled={looking} icon={<Search className="size-4" />}>
            Find
          </Button>
          <Button tone="ghost" onClick={() => setFields({})}>
            Clear
          </Button>
          <Switch checked={here} onChange={setHere} label={`Only around ${m.title}`} hint="Off searches every map's channels." />
          {here && (
            <Segmented
              label="Which channels on this map"
              value={grade}
              onChange={setGrade}
              options={[
                { value: "any", label: "All" },
                { value: "near", label: "Near" },
                ...(m.isOwn ? [{ value: "proven", label: "Send you viewers" }] : []),
              ]}
            />
          )}
          {here && kind === "channels" && (
            <Select
              label="Steps from this channel"
              value={steps}
              onChange={setSteps}
              options={[
                ["", "Any distance"],
                ["1", "Direct neighbours"],
                ["2", "Within 2 steps"],
                ["3", "Within 3 steps"],
              ]}
            />
          )}
        </div>
      </form>
      <p className="text-xs text-ink-3">{total == null ? "Searching" : `${total.toLocaleString()} found, ${shown.toLocaleString()} shown.`}</p>
      {total === 0 && <Empty title="Nothing matches" body="Loosen a filter, or turn off the map switch to search every map." />}
      {kind === "videos" ? (
        <div className="grid grid-cols-2 gap-x-4 gap-y-6 md:grid-cols-3 xl:grid-cols-4">
          {videos.map((v) => (
            <VideoCard
              key={v.id}
              v={v}
              sub={
                <span className="flex flex-col text-xs text-ink-3">
                  <span className="truncate">{count(v.channel_subscribers)} subscribers</span>
                  <span className="truncate">
                    {count(v.per_day)} a day{v.gaining != null ? ` · gaining ${count(v.gaining)} a day` : ""}
                    {v.similarity != null ? ` · ${Math.round(v.similarity * 100)} match` : ""}
                  </span>
                </span>
              }
            />
          ))}
        </div>
      ) : (
        channels.length > 0 && <ChannelTable rows={channels} />
      )}
      {more && (
        <div>
          <Button disabled={looking} onClick={() => void find({ ...fields, sort }, shown)}>
            Show more
          </Button>
        </div>
      )}
    </div>
  );
}

function ChannelTable({ rows }: { rows: FoundChannel[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] table-fixed text-sm">
        <thead className="text-left text-xs text-ink-3">
          <tr>
            <th className="py-1 font-medium">Channel</th>
            <th className="w-28 py-1 text-right font-medium">Started</th>
            <th className="w-24 py-1 text-right font-medium">Subscribers</th>
            <th className="w-24 py-1 text-right font-medium">Views, 30d</th>
            <th className="w-24 py-1 text-right font-medium">Usual video</th>
            <th className="w-20 py-1 text-right font-medium">Breakout</th>
            <th className="w-44 py-1 pl-4 font-medium">On your maps</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id} className="border-t border-line align-top">
              <td className="py-2 pr-2">
                <span className="flex min-w-0 items-center gap-2">
                  <Avatar src={c.avatar} size="size-6" />
                  <a href={youtubeChannel(c.id)} target="_blank" rel="noreferrer noopener" className="min-w-0 truncate text-ink hover:underline">
                    {c.title}
                  </a>
                  {c.matches > 0 && <span className="shrink-0 text-xs text-ink-3">{c.matches} titles match</span>}
                </span>
                {c.breakout_video && (
                  <a href={youtubeVideo(c.breakout_video.id)} target="_blank" rel="noreferrer noopener" className="mt-0.5 block max-w-full truncate pl-8 text-xs text-ink-3 hover:text-ink-2">
                    {count(c.breakout_video.views)} views: {c.breakout_video.title}
                  </a>
                )}
              </td>
              <td className="py-2 text-right text-ink-2">{startedAgo(c.started_at) ?? "Not read"}</td>
              <td className="py-2 text-right text-ink-2">{count(c.subscribers)}</td>
              <td className="py-2 text-right text-ink-2">{c.views_30d == null ? "Not read" : count(c.views_30d)}</td>
              <td className="py-2 text-right text-ink-2">{c.usual == null ? "Not read" : count(c.usual)}</td>
              <td className="py-2 text-right text-busy">{c.breakout ? times(c.breakout) : "–"}</td>
              <td className="py-2 pl-4 text-xs">
                <span className="flex flex-wrap gap-x-2 gap-y-0.5">
                  {c.maps.length === 0 && <span className="text-ink-3">–</span>}
                  {c.maps.map((x) => (
                    <Link key={x.map_id} to={`/c/${x.map_id}?channel=${encodeURIComponent(c.id)}`} className="text-ink-2 hover:text-ink hover:underline">
                      {x.map} <span className="text-ink-3">({x.proven ? `sent ${count(x.proven)}` : x.grade})</span>
                    </Link>
                  ))}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
