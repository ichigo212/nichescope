import { ExternalLink, Network, Plus, ScanSearch, Trash2, TrendingUp, TriangleAlert, Undo2, X } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { addCompetitors, createMap, expandAround, recheckMap, removeChannel, restoreChannel, setLearning, youtubeChannel } from "../../api";
import { MapFilters } from "../../components/MapFilters";
import { NO_FILTER, type MapFilter } from "../../components/mapFilter";
import { GRADE_CLASS, Legend, RadialMap } from "../../components/RadialMap";
import { Avatar, Badge, Button, OutLink, Switch, TextArea } from "../../components/ui";
import { VideoCard } from "../../components/VideoCard";
import { runJob, useJobEvents } from "../../events";
import { ago, count, percent, plural, startedAgo, times } from "../../format";
import { isNear, type MapChannel } from "../../types";
import { useMap, useMapChange } from "./context";

export function ChannelsTab() {
  const { m } = useMap();
  const [params, setParams] = useSearchParams();
  const picked = params.get("channel");
  const [showFar, setShowFar] = useState(false);
  const [filter, setFilter] = useState<MapFilter>(NO_FILTER);
  const pick = (id: string | null) => setParams(id ? { channel: id } : {}, { replace: true });
  const current = m.channels.find((c) => c.id === picked) ?? null;
  const near = m.channels.filter((c) => isNear(c) && !c.off).length;
  const onMap = m.channels.filter((c) => !c.off && (showFar || isNear(c)));

  return (
    <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(300px,360px)]">
      <div className="flex min-w-0 flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="min-w-0 text-sm text-ink-2">
            <span className="font-semibold text-ink">{near}</span> near channels
            <span className="mx-2 text-ink-3">·</span>
            <span className="font-semibold text-busy">{m.breakingOut}</span> breaking out this month
            <span className="mx-2 text-ink-3">·</span>
            <span className="text-ink-3">{plural(m.channels.length, "channel")} on the map</span>
          </p>
          <div className="flex items-center gap-3">
            <Switch checked={showFar} onChange={setShowFar} label="Far channels" />
            <MapFilters items={onMap} f={filter} setF={setFilter} />
          </div>
        </div>
        <div className="h-[clamp(420px,64vh,700px)] w-full rounded-lg border border-line bg-raised/40">
          <RadialMap m={m} showFar={showFar} selected={picked} onPick={pick} filter={filter} />
        </div>
        <Legend isOwn={m.isOwn} />
      </div>
      <aside className="flex min-w-0 flex-col gap-3">
        {current && <SelectedChannel c={current} onClose={() => pick(null)} />}
        <Confidence />
        <LearnList onPick={pick} picked={picked} />
        <AddCompetitors />
        <SetAside />
        <Removed />
      </aside>
    </section>
  );
}

function Confidence() {
  const { m, busy } = useMap();
  const c = m.confidence;
  if (!c) return null;
  return (
    <div className="rounded-md border border-busy/30 bg-busy/5 px-3 py-2.5 text-xs leading-relaxed text-ink-2">
      <TriangleAlert className="mr-1.5 -mt-0.5 inline size-3.5 text-busy" />
      Treat this map as a rough guide: {c.why}.{m.isOwn && " Channels with an amber ring come from your real traffic and are exact."}
      {c.instead && (
        <Button tone="ghost" className="mt-1.5 h-7 px-2 text-xs" disabled={busy} onClick={() => void runJob(createMap(c.instead!.id, 1))}>
          Map {c.instead.title} instead
        </Button>
      )}
    </div>
  );
}

function LearnList({ onPick, picked }: { onPick: (id: string) => void; picked: string | null }) {
  const { m, busy } = useMap();
  const change = useMapChange();
  const rows = useMemo(
    () => m.channels.filter(isNear).sort((a, b) => Number(a.off) - Number(b.off) || (b.proven ?? 0) - (a.proven ?? 0) || b.coverage - a.coverage),
    [m.channels],
  );
  const learning = rows.filter((c) => !c.off).length;
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-line bg-raised p-3">
      <p className="text-sm text-ink-2">
        <strong className="font-semibold text-ink">{learning}</strong> channels to learn from
        <span className="block text-xs text-ink-3">Topics, breakouts and answers use the checked channels.</span>
      </p>
      <ul className="flex max-h-[300px] flex-col overflow-y-auto pr-1">
        {rows.map((c) => (
          <li key={c.id} className={"group flex items-center gap-2 rounded-sm px-1 py-1 hover:bg-overlay " + (c.id === picked ? "bg-overlay" : "")}>
            <input
              type="checkbox"
              className="size-3.5 shrink-0 accent-[var(--color-accent)]"
              aria-label={`Learn from ${c.title}`}
              checked={!c.off}
              onChange={() => void change(setLearning(m.id, c.id, c.off))}
            />
            <Avatar src={c.avatar} className={c.off ? "opacity-40" : ""} />
            <button type="button" className={"min-w-0 flex-1 text-left " + (c.off ? "opacity-50" : "")} onClick={() => onPick(c.id)}>
              <span className="block truncate text-sm text-ink">{c.title}</span>
              <span className="block truncate text-xs">
                <span className={c.proven ? "text-busy" : GRADE_CLASS[c.grade]}>{c.proven ? `sends you ${count(c.proven)} views` : c.grade}</span>
                <span className="text-ink-3"> · {count(c.subscribers)}</span>
              </span>
            </button>
            <button
              type="button"
              aria-label={`Remove ${c.title} from this map`}
              title="Remove from this map"
              disabled={busy}
              className="inline-flex size-6 shrink-0 items-center justify-center rounded-sm text-ink-3 opacity-0 group-hover:opacity-100 hover:text-danger focus:opacity-100 disabled:opacity-30"
              onClick={() => void change(removeChannel(m.id, c.id))}
            >
              <X className="size-4" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AddCompetitors() {
  const { m, busy } = useMap();
  const [text, setText] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const job = useRef<string | null>(null);
  const names = text
    .split("\n")
    .map((n) => n.trim())
    .filter(Boolean);
  useJobEvents((e) => {
    if (e.job.id !== job.current || e.job.status === "running") return;
    job.current = null;
    setProblems(e.problems ?? []);
  });
  return (
    <form
      className="flex flex-col gap-2 rounded-lg border border-line bg-raised p-3"
      onSubmit={(e) => {
        e.preventDefault();
        setProblems([]);
        void runJob(addCompetitors(m.id, names)).then((started) => {
          if (!started) return;
          job.current = started.id;
          setText("");
        });
      }}
    >
      <p className="text-sm font-semibold text-ink">Add competitors</p>
      <TextArea rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder={"One per line: a name, link or @handle"} aria-label="Competitors, one per line" />
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-ink-3">Each one is read in full before it joins the map.</span>
        <Button type="submit" icon={<Plus className="size-4" />} disabled={busy || names.length === 0}>
          {names.length > 1 ? `Add ${names.length}` : "Add"}
        </Button>
      </div>
      {problems.length > 0 && (
        <ul className="flex flex-col gap-1 rounded-sm bg-danger/10 px-2.5 py-2 text-xs text-danger">
          {problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
    </form>
  );
}

function SelectedChannel({ c, onClose }: { c: MapChannel; onClose: () => void }) {
  const { m, busy } = useMap();
  const change = useMapChange();
  const expanded = m.expanded.includes(c.id);
  const started = startedAgo(c.startedAt);
  const stats: [string, string][] = [
    ["Subscribers", count(c.subscribers)],
    ["Views, 30 days", c.views30d == null ? "Not read" : count(c.views30d)],
    ["Started", started ?? "Unknown"],
    ["Biggest breakout", c.breakout ? times(c.breakout) : "None"],
  ];
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-line-strong bg-raised p-3">
      <div className="flex items-start gap-3">
        <Avatar src={c.avatar} size="size-12" />
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-base font-semibold text-ink">{c.title}</h3>
          <p className="truncate text-xs text-ink-3">{c.handle}</p>
        </div>
        <button type="button" aria-label="Close" className="rounded-sm p-1 text-ink-3 hover:bg-hover hover:text-ink" onClick={onClose}>
          <X className="size-4" />
        </button>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Badge tone={c.grade === "close" ? "accent" : c.grade === "medium" ? "sync" : "plain"}>{c.grade}</Badge>
        {c.proven != null && <Badge tone="busy">sent you {count(c.proven)} views</Badge>}
        {c.appearances > 0 && <Badge>beside {percent(c.coverage)} of videos read</Badge>}
        {c.via && !c.appearances && <Badge>found around {c.viaTitle ?? "a neighbour"}</Badge>}
        {c.added && <Badge>added by you</Badge>}
        {!c.added && c.fit === "same" && <Badge tone="accent">same kind of videos</Badge>}
        {!c.added && c.fit === "adjacent" && <Badge tone="sync">close to this niche</Badge>}
        {c.promoted != null && <Badge>linked from {c.promoted} neighbours</Badge>}
        {c.rising != null && Math.abs(c.rising) >= 0.01 && (
          <Badge tone={c.rising > 0 ? "accent" : "danger"}>
            <TrendingUp className="mr-1 inline size-3" />
            {c.rising > 0 ? "+" : ""}
            {percent(c.rising)} subscribers
          </Badge>
        )}
        {c.isNew && <Badge tone="accent">new this week</Badge>}
        {c.off && <Badge tone="danger">not learning</Badge>}
      </div>
      <dl className="grid grid-cols-2 gap-2">
        {stats.map(([k, v]) => (
          <div key={k} className="rounded-md bg-overlay px-3 py-2">
            <dt className="text-[11px] text-ink-3">{k}</dt>
            <dd className="text-sm font-semibold text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap gap-2">
        <Button icon={<Network className="size-4" />} disabled={busy || expanded} onClick={() => void runJob(expandAround(m.id, c.id))}>
          {expanded ? "Already mapped around" : "Map around it"}
        </Button>
        <OutLink tone="ghost" href={youtubeChannel(c.id)} icon={<ExternalLink className="size-4" />}>
          YouTube
        </OutLink>
        <Button tone="ghost" onClick={() => void change(setLearning(m.id, c.id, c.off))}>
          {c.off ? "Learn from it" : "Stop learning from it"}
        </Button>
        <Button tone="ghost" icon={<Trash2 className="size-4" />} disabled={busy} onClick={() => void change(removeChannel(m.id, c.id)).then((r) => r && onClose())}>
          Remove
        </Button>
      </div>
      {c.provenVideos.length > 0 && (
        <div className="flex flex-col gap-1">
          <h4 className="text-xs font-semibold text-ink-3">Its videos that send you viewers</h4>
          <ul className="flex flex-col gap-1 text-xs">
            {c.provenVideos.map((v) => (
              <li key={v.id} className="flex justify-between gap-3">
                <a className="min-w-0 truncate text-ink-2 hover:text-ink hover:underline" href={`https://www.youtube.com/watch?v=${v.id}`} target="_blank" rel="noreferrer">
                  {v.title}
                </a>
                <span className="shrink-0 text-busy">{count(v.views)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {c.breakouts.length > 0 ? (
        <div className="flex flex-col gap-2">
          <h4 className="text-xs font-semibold text-ink-3">Breakouts</h4>
          <div className="grid grid-cols-2 gap-3">
            {c.breakouts.slice(0, 4).map((v) => (
              <VideoCard key={v.id} v={v} />
            ))}
          </div>
        </div>
      ) : (
        <p className="text-xs text-ink-3">{c.usual == null ? "Not read in full yet." : "No video at three times its usual."}</p>
      )}
    </div>
  );
}

function SetAside() {
  const { m, busy } = useMap();
  return (
    <details className="rounded-lg border border-line bg-raised p-3">
      <summary className="text-sm text-ink-2 select-none hover:text-ink">
        {m.setAside.length ? plural(m.setAside.length, "channel") + " set aside" : "Nothing set aside"}{" "}
        <span className="text-xs text-ink-3">(judged to make something else)</span>
      </summary>
      <p className="mt-2 text-xs text-ink-3">
        Recommended beside this channel, but about another subject. Keep one to bring it back for good.
      </p>
      <ul className="mt-2 flex max-h-[220px] flex-col overflow-y-auto">
        {m.setAside.map((c) => (
          <li key={c.id} className="flex items-center gap-2 py-1 text-xs">
            <Avatar src={c.avatar} size="size-5" className="opacity-70" />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-ink-2">{c.title}</span>
              {c.seen && <span className="block truncate text-ink-3">{c.seen}</span>}
            </span>
            <button type="button" disabled={busy} className="shrink-0 text-sync hover:underline disabled:opacity-40" onClick={() => void runJob(addCompetitors(m.id, [c.id]))}>
              Keep
            </button>
          </li>
        ))}
      </ul>
      <Button tone="ghost" className="mt-2 h-7 px-2 text-xs" icon={<ScanSearch className="size-3.5" />} disabled={busy} onClick={() => void runJob(recheckMap(m.id))}>
        Check every channel again
      </Button>
    </details>
  );
}

function Removed() {
  const { m } = useMap();
  const change = useMapChange();
  if (!m.removed.length) return null;
  return (
    <details className="rounded-lg border border-line bg-raised p-3">
      <summary className="text-sm text-ink-2 select-none hover:text-ink">Removed from this map ({m.removed.length})</summary>
      <ul className="mt-2 flex flex-col">
        {m.removed.map((r) => (
          <li key={r.id} className="flex items-center justify-between gap-3 border-t border-line py-1.5 text-sm first:border-t-0">
            <span className="min-w-0 truncate text-ink-2">
              {r.title}
              {r.at && <span className="ml-2 text-xs text-ink-3">{ago(r.at)}</span>}
            </span>
            <Button tone="ghost" className="h-7 px-2" icon={<Undo2 className="size-3.5" />} onClick={() => void change(restoreChannel(m.id, r.id))}>
              Restore
            </Button>
          </li>
        ))}
      </ul>
    </details>
  );
}
