import { Globe, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { addCompetitors, youtubeChannel, youtubeSearch } from "../../../api";
import { Avatar, Button, Empty, Field, Input, Segmented, Select } from "../../../components/ui";
import { VideoCard } from "../../../components/VideoCard";
import { count } from "../../../format";
import { runJob } from "../../../events";
import { attempt } from "../../../toasts";
import type { LiveChannel, LiveMapPlace, LiveResults, LiveVideo } from "../../../types";
import { useMap } from "../context";

const SORTS: [string, string][] = [
  ["relevance", "Relevance"],
  ["views", "Most views"],
  ["date", "Newest"],
  ["rating", "Rating"],
];
const UPLOADED: [string, string][] = [
  ["any", "Any time"],
  ["hour", "Last hour"],
  ["today", "Today"],
  ["week", "This week"],
  ["month", "This month"],
  ["year", "This year"],
];
const LENGTHS: [string, string][] = [
  ["any", "Any length"],
  ["long", "Over 20 minutes"],
  ["medium", "4 to 20 minutes"],
  ["short", "Under 4 minutes"],
];
const PAGES: [string, string][] = [
  ["1", "About 20"],
  ["2", "About 40"],
  ["3", "About 60"],
];

function MapsLine({ maps }: { maps: LiveMapPlace[] }) {
  if (!maps.length) return null;
  return (
    <span className="flex flex-wrap gap-x-2 text-xs text-ink-3">
      On
      {maps.map((x) => (
        <Link key={x.mapId} to={`/c/${x.mapId}`} className="text-ink-2 hover:text-ink hover:underline">
          {x.map} ({x.grade === "own" ? "the channel" : (x.grade ?? "listed")})
        </Link>
      ))}
    </span>
  );
}

export function LiveSearch() {
  const { m, busy } = useMap();
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<"videos" | "channels">("videos");
  const [sort, setSort] = useState("relevance");
  const [uploaded, setUploaded] = useState("any");
  const [length, setLength] = useState("long");
  const [language, setLanguage] = useState("en");
  const [region, setRegion] = useState("US");
  const [pages, setPages] = useState("1");
  const [looking, setLooking] = useState(false);
  const [found, setFound] = useState<LiveResults | null>(null);
  const [added, setAdded] = useState<string[]>([]);

  const search = async () => {
    if (query.trim().length < 2) return;
    setLooking(true);
    const r = await attempt(youtubeSearch({ query: query.trim(), kind, sort, uploaded, length, language, region, pages: Number(pages) }));
    setLooking(false);
    if (r) setFound(r);
  };
  const add = (id: string) =>
    void runJob(addCompetitors(m.id, [id])).then((job) => {
      if (job) setAdded((a) => [...a, id]);
    });

  const videos = found?.kind === "videos" ? (found.results as LiveVideo[]) : null;
  const channels = found?.kind === "channels" ? (found.results as LiveChannel[]) : null;

  return (
    <div className="flex flex-col gap-4">
      <form
        className="flex flex-col gap-3 rounded-lg border border-line bg-raised p-4"
        onSubmit={(e) => {
          e.preventDefault();
          void search();
        }}
      >
        <div className="flex flex-wrap items-center gap-2">
          <Input className="min-w-72 flex-1" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search YouTube" aria-label="Search YouTube for" />
          <Segmented
            label="Search for"
            value={kind}
            onChange={setKind}
            options={[
              { value: "videos", label: "Videos" },
              { value: "channels", label: "Channels" },
            ]}
          />
          <Button type="submit" tone="primary" disabled={looking || query.trim().length < 2} icon={<Globe className="size-4" />}>
            {looking ? "Searching" : "Search YouTube"}
          </Button>
        </div>
        {kind === "videos" && (
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Field label="Order by">
              <Select label="Order by" value={sort} options={SORTS} onChange={setSort} />
            </Field>
            <Field label="Uploaded">
              <Select label="Uploaded" value={uploaded} options={UPLOADED} onChange={setUploaded} />
            </Field>
            <Field label="Length">
              <Select label="Length" value={length} options={LENGTHS} onChange={setLength} />
            </Field>
            <Field label="Results">
              <Select label="Results" value={pages} options={PAGES} onChange={setPages} />
            </Field>
            <Field label="Language">
              <Input value={language} onChange={(e) => setLanguage(e.target.value)} placeholder="en" />
            </Field>
            <Field label="Region">
              <Input value={region} onChange={(e) => setRegion(e.target.value)} placeholder="US" />
            </Field>
          </div>
        )}
        <p className="text-xs text-ink-3">Uses no quota. Times usual is shown for channels the maps have already read.</p>
      </form>
      {found?.note && <p className="text-sm text-ink-3">{found.note}</p>}
      {videos && (
        <>
          <p className="text-xs text-ink-3">
            {videos.length} videos, {found!.judged} from channels the maps have read.
          </p>
          {videos.length === 0 && !found?.note && <Empty title="Nothing found" body="Try fewer words or a longer time." />}
          <div className="grid grid-cols-2 gap-x-4 gap-y-6 md:grid-cols-3 xl:grid-cols-4">
            {videos.map((v) => (
              <div key={v.id} className="flex min-w-0 flex-col gap-1">
                <VideoCard v={{ ...v, published_at: undefined, channel: undefined }} sub={<span className="text-xs text-ink-3">{v.live ? "Live" : v.age_text}</span>} />
                <span className="flex min-w-0 items-center gap-2 text-xs text-ink-3">
                  <a href={youtubeChannel(v.channel_id)} target="_blank" rel="noreferrer noopener" className="min-w-0 truncate hover:text-ink-2">
                    {v.channel}
                    {v.channel_subscribers != null ? ` · ${count(v.channel_subscribers)} subscribers` : ""}
                  </a>
                  {v.maps.length === 0 && v.channel_id && (
                    <button
                      type="button"
                      disabled={busy || added.includes(v.channel_id)}
                      title={`Add ${v.channel} to ${m.title}'s map`}
                      className="inline-flex shrink-0 items-center gap-0.5 rounded-sm px-1 text-accent hover:bg-overlay disabled:text-ink-3"
                      onClick={() => add(v.channel_id)}
                    >
                      <Plus className="size-3" />
                      {added.includes(v.channel_id) ? "Added" : "Add"}
                    </button>
                  )}
                </span>
                <MapsLine maps={v.maps} />
              </div>
            ))}
          </div>
        </>
      )}
      {channels && (
        <>
          {channels.length === 0 && <Empty title="No channels found" body="Try another name." />}
          <ul className="flex flex-col">
            {channels.map((c) => (
              <li key={c.id} className="flex items-center gap-3 border-t border-line py-2 text-sm">
                <Avatar src={c.avatar} size="size-8" />
                <span className="min-w-0 flex-1">
                  <a href={youtubeChannel(c.id)} target="_blank" rel="noreferrer noopener" className="block max-w-full truncate text-ink hover:underline">
                    {c.title.trim()}
                  </a>
                  <span className="block truncate text-xs text-ink-3">
                    {c.detail}
                    {c.usual != null ? ` · usual video ${count(c.usual)}` : ""}
                  </span>
                  <MapsLine maps={c.maps} />
                </span>
                {c.maps.length === 0 && (
                  <Button tone="ghost" icon={<Plus className="size-4" />} disabled={busy || added.includes(c.id)} onClick={() => add(c.id)}>
                    {added.includes(c.id) ? "Added" : `Add to ${m.title}`}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
