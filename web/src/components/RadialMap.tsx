import { Minus, Plus } from "lucide-react";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { percent, times } from "../format";
import { isNear, type Grade, type MapChannel, type NicheMap } from "../types";
import { NO_FILTER, passes, type MapFilter } from "./mapFilter";

/** Links at least this strong are drawn faintly even when nothing is in focus. */
const STRONG_LINK = 0.5;

const GRADES: Grade[] = ["close", "medium", "far"];
export const GRADE_CLASS: Record<Grade, string> = { close: "text-accent", medium: "text-sync", far: "text-ink-3" };
const GOLDEN = Math.PI * (3 - Math.sqrt(5));
/** More far channels than this are drawn as plain dots: hundreds of pictures are slow. */
const FAR_PICTURES = 100;
const CENTRE_R = 34;
const SPACING = 5;
const STRETCH = 1.5;
const SETTLE_STEPS = 60;
const BADGES = 6;

interface Spot {
  c: MapChannel;
  x: number;
  y: number;
  r: number;
}

/** Bigger circles, more views this month: who is winning now. Without a month, a tenth of subscribers stands in. */
function radius(c: MapChannel) {
  const month = c.views30d ?? (c.subscribers != null ? c.subscribers / 10 : null);
  const s = Math.log10(Math.max(month ?? 10, 10));
  return c.grade === "far" ? 4 + s * 0.8 : 7 + s * 2.2;
}

/** The nearest channels sit in the middle and each grade fills the band around the last,
 *  seeded as a sunflower. Links then pull channels that recommend each other together,
 *  within their band, so distance from the middle always means closeness. Deterministic. */
function layout(m: NicheMap, showFar: boolean) {
  const shown = m.channels
    .filter((c) => !c.off && (showFar || isNear(c)))
    .sort(
      (a, b) =>
        GRADES.indexOf(a.grade) - GRADES.indexOf(b.grade) ||
        (b.proven ?? 0) - (a.proven ?? 0) ||
        b.coverage - a.coverage ||
        (b.subscribers ?? 0) - (a.subscribers ?? 0),
    );
  let area = Math.PI * (CENTRE_R + 14) ** 2;
  const band: Partial<Record<Grade, [number, number]>> = {};
  const spots: Spot[] = shown.map((c, i) => {
    const r = radius(c);
    area += Math.PI * (r + SPACING) ** 2 * 1.3;
    const d = Math.sqrt(area / Math.PI);
    band[c.grade] = [band[c.grade]?.[0] ?? d, d];
    return { c, r, x: Math.cos(i * GOLDEN) * d, y: Math.sin(i * GOLDEN) * d };
  });
  const at = new Map(spots.map((s) => [s.c.id, s]));
  const pairs = m.links.flatMap((l) => {
    const a = at.get(l.a);
    const b = at.get(l.b);
    return a && b ? [[a, b] as const] : [];
  });
  for (let step = 0; step < SETTLE_STEPS; step++) {
    const pull = 0.03 * (1 - step / SETTLE_STEPS);
    for (const [a, b] of pairs) {
      const dx = (b.x - a.x) * pull;
      const dy = (b.y - a.y) * pull;
      a.x += dx;
      a.y += dy;
      b.x -= dx;
      b.y -= dy;
    }
    for (let i = 0; i < spots.length; i++) {
      const a = spots[i]!;
      for (let j = i + 1; j < spots.length; j++) {
        const b = spots[j]!;
        const need = a.r + b.r + SPACING;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        if (Math.abs(dx) >= need || Math.abs(dy) >= need) continue;
        const dist = Math.hypot(dx, dy);
        if (!dist || dist >= need) continue;
        const push = (need - dist) / dist / 2;
        a.x -= dx * push;
        a.y -= dy * push;
        b.x += dx * push;
        b.y += dy * push;
      }
    }
    for (const s of spots) {
      const [low, high] = band[s.c.grade]!;
      const d = Math.hypot(s.x, s.y) || 1;
      const kept = Math.min(high + 6, Math.max(low - 6, CENTRE_R + s.r + 6, d));
      s.x *= kept / d;
      s.y *= kept / d;
    }
  }
  let wide = 120;
  let tall = 120;
  for (const s of spots) {
    s.x *= STRETCH;
    wide = Math.max(wide, Math.abs(s.x) + s.r);
    tall = Math.max(tall, Math.abs(s.y) + s.r);
  }
  const rings = GRADES.flatMap((grade) => {
    const b = band[grade];
    return b ? [{ grade, r: b[1] + 14 }] : [];
  });
  return { spots, rings, w: (wide + 36) * 2, h: (tall + 36) * 2 };
}

const Node = memo(function Node({
  s,
  selected,
  picture,
  dim,
  onPick,
  onHover,
}: {
  s: Spot;
  selected: boolean;
  picture: boolean;
  dim: boolean;
  onPick: (id: string) => void;
  onHover: (id: string | null) => void;
}) {
  const { c, x, y, r } = s;
  return (
    <g
      opacity={dim ? 0.15 : 1}
      role="button"
      aria-label={c.title}
      tabIndex={0}
      className={"cursor-pointer outline-none " + GRADE_CLASS[c.grade]}
      onClick={() => onPick(c.id)}
      onKeyDown={(e) => e.key === "Enter" && onPick(c.id)}
      onPointerEnter={() => onHover(c.id)}
      onPointerLeave={() => onHover(null)}
    >
      <title>{`${c.title}${c.proven ? `: sent you ${c.proven} views` : c.appearances ? `: beside ${percent(c.coverage)} of the videos read` : ""}`}</title>
      {c.avatar && picture ? (
        <image href={c.avatar} x={x - r} y={y - r} width={r * 2} height={r * 2} clipPath="url(#map-disc)" opacity={c.grade === "far" ? 0.7 : 1} />
      ) : (
        <circle cx={x} cy={y} r={r} fill="currentColor" opacity={0.45} />
      )}
      <circle
        cx={x}
        cy={y}
        r={r}
        fill="none"
        stroke="currentColor"
        className={selected ? "text-ink" : c.proven ? "text-busy" : undefined}
        // the more viewers it really sends, the heavier its ring
        strokeWidth={selected ? 3.5 : c.proven ? 1 + Math.min(Math.log10(c.proven + 1), 2) * 1.2 : 1.2}
      />
    </g>
  );
});

/** The channels around a map's channel, nearest in the middle. Drag to move; buttons or the wheel zoom. */
export function RadialMap({
  m,
  showFar,
  selected,
  onPick,
  filter = NO_FILTER,
}: {
  m: NicheMap;
  showFar: boolean;
  selected: string | null;
  onPick: (id: string) => void;
  filter?: MapFilter;
}) {
  const { spots: every, rings, w, h } = useMemo(() => layout(m, showFar), [m, showFar]);
  const keep = useCallback((c: MapChannel) => passes(c, filter), [filter]);
  const spots = useMemo(() => (filter.leftOut === "hide" ? every.filter((s) => keep(s.c)) : every), [every, filter.leftOut, keep]);
  const at = useMemo(() => new Map(spots.map((s) => [s.c.id, s])), [spots]);
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const [box, setBox] = useState({ w: 1000, h: 500 });
  const [hover, setHover] = useState<string | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const justDragged = useRef(false);

  const vw = w / view.k;
  const vh = h / view.k;
  const unit = 1 / Math.min(box.w / vw, box.h / vh);

  useEffect(() => {
    setView({ x: 0, y: 0, k: 1 });
  }, [m.id]);

  useEffect(() => {
    const el = svg.current;
    if (!el) return;
    const read = () => setBox({ w: el.clientWidth || 1000, h: el.clientHeight || 500 });
    read();
    const watch = new ResizeObserver(read);
    watch.observe(el);
    return () => watch.disconnect();
  }, []);

  useEffect(() => {
    const el = svg.current;
    if (!el) return;
    // Zoom only with Ctrl held: a plain wheel keeps scrolling the page.
    const wheel = (e: globalThis.WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const px = e.clientX - rect.left - rect.width / 2;
      const py = e.clientY - rect.top - rect.height / 2;
      const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      setView((v) => {
        const k = Math.min(12, Math.max(1, v.k * factor));
        const before = Math.min(rect.width / (w / v.k), rect.height / (h / v.k));
        const after = Math.min(rect.width / (w / k), rect.height / (h / k));
        return { k, x: v.x + px / before - px / after, y: v.y + py / before - py / after };
      });
    };
    el.addEventListener("wheel", wheel, { passive: false });
    return () => el.removeEventListener("wheel", wheel);
  }, [w, h]);

  const pick = useCallback(
    (id: string) => {
      // the end of a drag also fires a click: that is not a choice
      if (justDragged.current) justDragged.current = false;
      else onPick(id);
    },
    [onPick],
  );
  const lines = useMemo(
    () =>
      // Only the strongest links show at rest, faintly; pointing at a channel shows all of its links.
      m.links.filter((l) => l.coverage >= STRONG_LINK).map((l) => {
        const a = at.get(l.a);
        const b = at.get(l.b);
        if (!a || !b) return null;
        return <line key={`${l.a}-${l.b}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="stroke-sync" strokeOpacity={0.05 + (l.coverage - STRONG_LINK) * 0.2} />;
      }),
    [m.links, at],
  );
  const nodes = useMemo(() => {
    const pictures = spots.filter((s) => s.c.grade === "far").length <= FAR_PICTURES;
    return spots.map((s) => (
      <Node key={s.c.id} s={s} selected={s.c.id === selected} picture={s.c.grade !== "far" || pictures} dim={!keep(s.c)} onPick={pick} onHover={setHover} />
    ));
  }, [spots, selected, pick, keep]);
  const badges = useMemo(
    () =>
      spots
        .filter((s) => filter.badges && keep(s.c) && s.c.grade !== "far" && (s.c.breakout ?? 0) >= filter.badgeMin)
        .sort((a, b) => b.c.breakout! - a.c.breakout!)
        .slice(0, BADGES)
        .map(({ c, x, y, r }) => (
          <g key={c.id} className="pointer-events-none">
            <rect x={x + r - 8} y={y - r - 9} width={38} height={17} rx={8.5} className="fill-overlay stroke-busy" />
            <text x={x + r + 11} y={y - r + 3.5} textAnchor="middle" fontSize={11} fontWeight={700} className="fill-busy">
              {times(c.breakout!)}
            </text>
          </g>
        )),
    [spots, filter.badges, filter.badgeMin, keep],
  );

  const focus = [selected, hover].filter((id, i, all): id is string => !!id && all.indexOf(id) === i);
  const moved = view.k !== 1 || view.x !== 0 || view.y !== 0;
  const zoom = (factor: number) => setView((v) => ({ ...v, k: Math.min(12, Math.max(1, v.k * factor)) }));
  const label = (x: number, y: number, text: string, key: string, strong = false) => (
    <text
      key={key}
      x={x}
      y={y}
      textAnchor="middle"
      fontSize={12.5 * unit}
      fontWeight={strong ? 700 : 600}
      className="pointer-events-none fill-ink"
      stroke="var(--color-base)"
      strokeWidth={3.5 * unit}
      paintOrder="stroke"
    >
      {text}
    </text>
  );
  const control = "rounded-sm border border-line-strong bg-overlay p-1 text-ink-2 hover:text-ink";

  return (
    <div className="relative h-full w-full">
      <div className="absolute top-2 right-2 z-10 flex items-center gap-1">
        {moved && (
          <button type="button" className="rounded-sm border border-line-strong bg-overlay px-2.5 py-1 text-xs font-semibold text-ink hover:bg-hover" onClick={() => setView({ x: 0, y: 0, k: 1 })}>
            Fit
          </button>
        )}
        <button type="button" aria-label="Zoom in" className={control} onClick={() => zoom(1.3)}>
          <Plus className="size-4" />
        </button>
        <button type="button" aria-label="Zoom out" className={control} onClick={() => zoom(1 / 1.3)}>
          <Minus className="size-4" />
        </button>
      </div>
      <svg
        ref={svg}
        viewBox={`${view.x - vw / 2} ${view.y - vh / 2} ${vw} ${vh}`}
        className="h-full w-full cursor-grab touch-none select-none"
        role="img"
        aria-label={`Channels around ${m.title}`}
        onPointerDown={(e) => {
          drag.current = { x: e.clientX, y: e.clientY, moved: false };
          justDragged.current = false;
        }}
        onPointerMove={(e) => {
          const d = drag.current;
          if (!d) return;
          const dx = e.clientX - d.x;
          const dy = e.clientY - d.y;
          if (!d.moved && Math.abs(dx) + Math.abs(dy) < 4) return;
          d.moved = true;
          d.x = e.clientX;
          d.y = e.clientY;
          setView((v) => ({ ...v, x: v.x - dx * unit, y: v.y - dy * unit }));
        }}
        onPointerUp={() => {
          justDragged.current = !!drag.current?.moved;
          drag.current = null;
        }}
        onPointerLeave={() => (drag.current = null)}
      >
        <defs>
          <clipPath id="map-disc" clipPathUnits="objectBoundingBox">
            <circle cx={0.5} cy={0.5} r={0.5} />
          </clipPath>
          <radialGradient id="map-glow">
            <stop offset="0%" stopColor="var(--color-sync)" stopOpacity={0.12} />
            <stop offset="100%" stopColor="var(--color-sync)" stopOpacity={0} />
          </radialGradient>
        </defs>
        <ellipse rx={w / 2} ry={h / 2} fill="url(#map-glow)" />
        {rings.map(({ grade, r }) => (
          <ellipse key={grade} rx={r * STRETCH} ry={r} fill="none" stroke="currentColor" className={GRADE_CLASS[grade]} strokeOpacity={0.28} strokeDasharray="4 8" />
        ))}
        {lines}
        {focus.flatMap((id) =>
          m.links
            .filter((l) => (l.a === id || l.b === id) && at.has(l.a) && at.has(l.b))
            .map((l) => {
              const a = at.get(l.a)!;
              const b = at.get(l.b)!;
              return <line key={`hot-${id}-${l.a}-${l.b}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="stroke-accent" strokeWidth={1.5} strokeOpacity={0.85} />;
            }),
        )}
        {nodes}
        <g className="text-ink">
          {m.avatar ? (
            <image href={m.avatar} x={-CENTRE_R} y={-CENTRE_R} width={CENTRE_R * 2} height={CENTRE_R * 2} clipPath="url(#map-disc)" />
          ) : (
            <circle r={CENTRE_R} className="fill-overlay" />
          )}
          <circle r={CENTRE_R} fill="none" stroke="currentColor" strokeWidth={2} />
        </g>
        {badges}
        {label(0, CENTRE_R + 16 * unit, m.title, "centre", true)}
        {focus.map((id) => {
          const s = at.get(id);
          return s ? label(s.x, s.y - s.r - 6 * unit, s.c.title, `name-${id}`) : null;
        })}
      </svg>
    </div>
  );
}

export function Legend({ isOwn }: { isOwn: boolean }) {
  const dot = (cls: string) => <span className={"inline-block size-2.5 rounded-full border-2 " + cls} />;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-3">
      <span>Nearer the middle, nearer this channel</span>
      <span className="inline-flex items-center gap-1.5">{dot("border-accent")} close</span>
      <span className="inline-flex items-center gap-1.5">{dot("border-sync")} medium</span>
      <span className="inline-flex items-center gap-1.5">{dot("border-ink-3")} far</span>
      {isOwn && <span className="inline-flex items-center gap-1.5">{dot("border-busy")} sends you viewers</span>}
      <span>Size: views in the last 30 days</span>
      <span>Ctrl and scroll to zoom</span>
    </div>
  );
}
