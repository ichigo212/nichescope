export const count = (n: number | null | undefined) => {
  if (n == null) return "?";
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(n >= 1e7 ? 0 : 1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(n >= 1e4 ? 0 : 1)}K`;
  return String(Math.round(n));
};

export const times = (x: number) => (x >= 10 ? `${Math.round(x)}×` : `${x.toFixed(1)}×`);

export const percent = (x: number) => `${Math.round(x * 100)}%`;

export const ageDays = (iso: string) => (Date.now() - new Date(iso).getTime()) / 86400000;

export function ago(iso: string | null | undefined) {
  if (!iso) return "";
  const d = Math.floor(ageDays(iso));
  if (!Number.isFinite(d)) return "";
  const say = (n: number, unit: string) => `${n} ${unit}${n === 1 ? "" : "s"} ago`;
  if (d < 1) return "today";
  if (d < 14) return say(d, "day");
  if (d < 60) return say(Math.round(d / 7), "week");
  if (d < 365) return say(Math.round(d / 30), "month");
  return say(Math.round(d / 365), "year");
}

/** "started 14 months ago", from a channel's first upload date. */
export function startedAgo(iso: string | null | undefined) {
  if (!iso) return null;
  const months = Math.floor(ageDays(iso) / 30.44);
  if (!Number.isFinite(months)) return null;
  if (months < 1) return "less than a month ago";
  return `${months} month${months === 1 ? "" : "s"} ago`;
}

export function duration(seconds: number) {
  const pad = (n: number) => String(n).padStart(2, "0");
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

export const when = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

export const plural = (n: number, word: string, many = `${word}s`) => `${n.toLocaleString()} ${n === 1 ? word : many}`;

/** A video id from a link (watch, youtu.be, shorts, embed, live) or a bare id. */
export function videoId(text: string): string | null {
  const t = text.trim();
  if (/^[\w-]{11}$/.test(t)) return t;
  const m = /(?:[?&]v=|youtu\.be\/|\/shorts\/|\/embed\/|\/live\/|\/v\/)([\w-]{11})/.exec(t);
  return m ? m[1]! : null;
}
