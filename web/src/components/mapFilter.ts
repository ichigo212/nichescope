/** What a map or the mesh shows. A channel nothing is known about passes. */
export interface MapFilter {
  subs: "any" | "10000" | "50000" | "500000";
  views: "any" | "10000" | "100000" | "1000000";
  length: "any" | "short" | "mid" | "long" | "vlong";
  language: string;
  badges: boolean;
  /** smallest breakout, in times usual, that gets a badge */
  badgeMin: number;
  leftOut: "dim" | "hide";
}

export interface Filterable {
  subscribers: number | null;
  views30d: number | null;
  minutes: number | null;
  language: string;
}

export const NO_FILTER: MapFilter = { subs: "any", views: "any", length: "any", language: "any", badges: true, badgeMin: 10, leftOut: "dim" };

const LENGTHS: Record<MapFilter["length"], [number, number]> = {
  any: [0, 1e9],
  short: [0, 15],
  mid: [15, 30],
  long: [30, 60],
  vlong: [60, 1e9],
};

export function passes(c: Filterable, f: MapFilter) {
  if (f.subs !== "any" && c.subscribers != null && c.subscribers >= Number(f.subs)) return false;
  if (f.views !== "any" && c.views30d != null && c.views30d < Number(f.views)) return false;
  const [lo, hi] = LENGTHS[f.length];
  if (f.length !== "any" && c.minutes != null && (c.minutes < lo || c.minutes >= hi)) return false;
  if (f.language !== "any" && (c.language || "") !== (f.language === "unknown" ? "" : f.language)) return false;
  return true;
}

export function filtersOn(f: MapFilter) {
  return [f.subs !== "any", f.views !== "any", f.length !== "any", f.language !== "any", !f.badges, f.badgeMin !== NO_FILTER.badgeMin].filter(Boolean)
    .length;
}
