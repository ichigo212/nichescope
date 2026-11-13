import { Crosshair, ExternalLink, Map as MapIcon, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { getMesh, youtubeChannel } from "../api";
import { MapFilters } from "../components/MapFilters";
import { NO_FILTER, passes, type MapFilter } from "../components/mapFilter";
import { FIT_COLOURS, MeshScene } from "../components/MeshScene";
import { Avatar, Badge, Empty, Loading, OutLink, Select, Slider, buttonClass } from "../components/ui";
import { count, plural, startedAgo, times } from "../format";
import { attempt } from "../toasts";
import type { Mesh, MeshNode } from "../types";

const PANEL = "rounded-xl border border-white/8 bg-[#0a0f1a]/75 shadow-[0_12px_40px_rgba(0,0,0,0.45)] backdrop-blur-md";

export function MeshPage() {
  const [params, setParams] = useSearchParams();
  const centre = params.get("center");
  const [mesh, setMesh] = useState<Mesh | null>(null);
  const [loading, setLoading] = useState(true);
  const [depth, setDepth] = useState(2);
  const [filter, setFilter] = useState<MapFilter>(NO_FILTER);
  const [selected, setSelected] = useState<string | null>(null);
  const loaded = useRef<string | null>(null);

  useEffect(() => {
    if (centre && loaded.current === centre) return;
    let live = true;
    setLoading(true);
    void attempt(getMesh(centre)).then((got) => {
      if (!live) return;
      setLoading(false);
      if (!got) return;
      loaded.current = got.center;
      setSelected(null);
      setMesh(got);
      if (got.center && got.center !== centre) setParams({ center: got.center }, { replace: true });
    });
    return () => {
      live = false;
    };
  }, [centre, setParams]);

  const inDepth = useMemo(
    () => mesh?.nodes.filter((n) => n.id === mesh.center || (n.step != null && n.step <= depth)) ?? [],
    [mesh, depth],
  );
  const failing = useMemo(
    () => new Set(inDepth.filter((n) => n.id !== mesh?.center && !passes(n, filter)).map((n) => n.id)),
    [inDepth, filter, mesh],
  );
  const dimmed = useMemo(() => (filter.leftOut === "dim" ? failing : new Set<string>()), [failing, filter.leftOut]);
  const hidden = useMemo(() => (filter.leftOut === "hide" ? failing : new Set<string>()), [failing, filter.leftOut]);

  if (!mesh || !mesh.center) {
    if (loading) return <div className="px-6 pt-8"><Loading text="Loading every map" /></div>;
    return (
      <div className="px-6 pt-8">
        <Empty title="No maps yet" body="Map a channel first. The mesh joins every map into one graph." action={<Link to="/" className={buttonClass("secondary")}>Add a channel</Link>} />
      </div>
    );
  }

  const shown = inDepth.length - failing.size;
  const maxStep = Math.max(1, ...mesh.nodes.map((n) => n.step ?? 0));
  const node = mesh.nodes.find((n) => n.id === selected) ?? null;
  const centreTitle = mesh.nodes.find((n) => n.id === mesh.center)?.title ?? "";

  return (
    <div className="mesh-stage relative h-full min-h-0 overflow-hidden">
      <MeshScene
        nodes={mesh.nodes}
        links={mesh.links}
        centre={mesh.center}
        depth={depth}
        dimmed={dimmed}
        hidden={hidden}
        badges={filter.badges}
        badgeMin={filter.badgeMin}
        selected={selected}
        onSelect={setSelected}
      />

      <div className={`${PANEL} absolute top-4 left-4 flex w-72 flex-col gap-3 p-4`}>
        <Select
          label="Centre"
          value={mesh.maps.some((x) => x.id === mesh.center) ? mesh.center : ""}
          onChange={(v) => v && setParams({ center: v })}
          options={[
            ...(mesh.maps.some((x) => x.id === mesh.center) ? [] : [["", centreTitle] as [string, string]]),
            ...mesh.maps.map((x): [string, string] => [x.id, x.title]),
          ]}
        />
        <p className="text-sm text-ink-2">
          <strong className="font-semibold text-ink">{shown.toLocaleString()}</strong> of {plural(mesh.nodes.length, "channel")}
          {loading && <span className="ml-2 text-ink-3">updating</span>}
        </p>
      </div>

      <div className={`${PANEL} absolute top-4 right-4 flex items-center gap-4 px-4 py-2.5`}>
        <div className="flex w-60 items-center gap-3 pr-3">
          <span className="text-sm text-ink-2">Depth</span>
          <Slider label="Depth" min={1} max={5} value={depth} onChange={setDepth} format={(v) => `${v}`} />
        </div>
        <MapFilters items={inDepth} f={filter} setF={setFilter} />
      </div>
      {depth > maxStep && (
        <p className="absolute top-20 right-4 text-xs text-ink-3">Nothing is linked more than {plural(maxStep, "step")} out.</p>
      )}

      {node && (
        <div className={`${PANEL} mesh-card absolute right-4 bottom-4 w-[340px] p-4`}>
          <NodePanel node={node} maps={mesh.maps} onClose={() => setSelected(null)} onCentre={(id) => setParams({ center: id })} />
        </div>
      )}

      <div className="pointer-events-none absolute bottom-4 left-4 flex flex-col gap-1.5 text-xs text-ink-3">
        <Legend />
        <span>Drag to turn, scroll to zoom. Point at a channel to see all its links; click to fly to it.</span>
      </div>
    </div>
  );
}

function Legend() {
  const ring = (colour: string) => <span className="inline-block size-2.5 rounded-full border-2" style={{ borderColor: colour }} />;
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1">
      <span className="inline-flex items-center gap-1.5">{ring(FIT_COLOURS.same)} same kind of videos</span>
      <span className="inline-flex items-center gap-1.5">{ring(FIT_COLOURS.adjacent)} close to it</span>
      <span className="inline-flex items-center gap-1.5">{ring(FIT_COLOURS.other)} not judged yet</span>
      <span>each ring is one step further out; size is views in 30 days</span>
    </div>
  );
}

function NodePanel({ node, maps, onClose, onCentre }: { node: MeshNode; maps: Mesh["maps"]; onClose: () => void; onCentre: (id: string) => void }) {
  const isMap = maps.some((x) => x.id === node.id);
  const on = maps.filter((x) => node.maps.includes(x.id) && x.id !== node.id);
  const stats: [string, string][] = [
    ["Steps from centre", node.step == null ? "Not linked" : String(node.step)],
    ["Subscribers", count(node.subscribers)],
    ["Views, 30 days", node.views30d == null ? "Not read" : count(node.views30d)],
    ["Started", startedAgo(node.startedAt) ?? "Unknown"],
    ["Best lately", node.breakout ? `${times(node.breakout)} its usual` : "None"],
    ["Average length", node.minutes ? `${node.minutes} min` : "Unknown"],
  ];
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-start gap-3">
        <Avatar src={node.avatar} size="size-11" />
        <div className="min-w-0 flex-1">
          <h2 className="truncate font-semibold text-ink">{node.title}</h2>
          <p className="truncate text-xs text-ink-3">{node.handle}</p>
        </div>
        <button type="button" aria-label="Close" className="rounded-sm p-1 text-ink-3 hover:bg-white/5 hover:text-ink" onClick={onClose}>
          <X className="size-4" />
        </button>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {isMap && <Badge tone="accent">Mapped</Badge>}
        {node.mapped && !isMap && <Badge tone="sync">Mapped around</Badge>}
        {node.language && <Badge>{node.language.toUpperCase()}</Badge>}
        {node.off && <Badge tone="danger">Excluded on a map</Badge>}
      </div>
      <dl className="grid grid-cols-2 gap-2">
        {stats.map(([k, v]) => (
          <div key={k} className="rounded-md bg-white/[0.04] px-3 py-2">
            <dt className="text-[11px] text-ink-3">{k}</dt>
            <dd className="text-sm font-semibold text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={buttonClass("secondary")} onClick={() => onCentre(node.id)}>
          <Crosshair className="size-4" />
          Center here
        </button>
        {isMap && (
          <Link to={`/c/${node.id}`} className={buttonClass("secondary")}>
            <MapIcon className="size-4" />
            Open map
          </Link>
        )}
        <OutLink tone="ghost" href={youtubeChannel(node.id)} icon={<ExternalLink className="size-4" />}>
          YouTube
        </OutLink>
      </div>
      {on.length > 0 && (
        <div className="flex flex-col gap-1 border-t border-white/8 pt-3 text-xs">
          <p className="text-ink-3">On {plural(on.length, "map")}</p>
          {on.map((x) => (
            <Link key={x.id} to={`/c/${x.id}?channel=${encodeURIComponent(node.id)}`} className="truncate text-ink-2 hover:text-ink hover:underline">
              {x.title}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
