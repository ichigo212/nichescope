import { SlidersHorizontal } from "lucide-react";
import { useState, type ReactNode } from "react";

import { NO_FILTER, filtersOn, passes, type Filterable, type MapFilter } from "./mapFilter";
import { Button, Segmented, Switch } from "./ui";

/** The filter panel for a map or the mesh: who is shown, and how the rest look. */
export function MapFilters({ items, f, setF, align = "right" }: { items: Filterable[]; f: MapFilter; setF: (f: MapFilter) => void; align?: "left" | "right" }) {
  const [open, setOpen] = useState(false);
  const langs = new Map<string, number>();
  items.forEach((c) => langs.set(c.language || "unknown", (langs.get(c.language || "unknown") ?? 0) + 1));
  const shown = items.filter((c) => passes(c, f)).length;
  const on = filtersOn(f);
  const chip = <K extends keyof MapFilter>(key: K, value: MapFilter[K], label: string) => (
    <button
      key={String(value)}
      type="button"
      aria-pressed={f[key] === value}
      onClick={() => setF({ ...f, [key]: value })}
      className={"rounded-full border px-2.5 py-1 text-xs " + (f[key] === value ? "border-sync bg-sync/15 text-ink" : "border-line-strong text-ink-2 hover:text-ink")}
    >
      {label}
    </button>
  );
  const group = (title: string, chips: ReactNode) => (
    <div className="flex flex-col gap-1.5">
      <p className="text-xs text-ink-3">{title}</p>
      <div className="flex flex-wrap gap-1.5">{chips}</div>
    </div>
  );
  return (
    <div className="relative">
      <Button icon={<SlidersHorizontal className="size-4" />} onClick={() => setOpen(!open)} aria-expanded={open}>
        Filters{on ? ` (${on})` : ""}
      </Button>
      {open && (
        <>
          <button type="button" aria-label="Close the filters" className="fixed inset-0 z-20 cursor-default" onClick={() => setOpen(false)} />
          <div
            className={
              "absolute top-full z-30 mt-1 flex w-80 flex-col gap-3 rounded-lg border border-line-strong bg-overlay p-3 text-sm shadow-xl " +
              (align === "right" ? "right-0" : "left-0")
            }
          >
            {group("Subscribers", [chip("subs", "any", "Any"), chip("subs", "10000", "Under 10K"), chip("subs", "50000", "Under 50K"), chip("subs", "500000", "Under 500K")])}
            {group("Views in the last 30 days", [chip("views", "any", "Any"), chip("views", "10000", "10K+"), chip("views", "100000", "100K+"), chip("views", "1000000", "1M+")])}
            {group("Average video length", [
              chip("length", "any", "Any"),
              chip("length", "short", "Under 15 min"),
              chip("length", "mid", "15–30 min"),
              chip("length", "long", "30–60 min"),
              chip("length", "vlong", "Over 1 h"),
            ])}
            {group("Language", [
              chip("language", "any", "Any"),
              ...[...langs.entries()]
                .sort((a, b) => b[1] - a[1])
                .slice(0, 8)
                .map(([code, n]) => chip("language", code, `${code === "unknown" ? "Unknown" : code.toUpperCase()} ${n}`)),
            ])}
            <Switch checked={f.badges} onChange={(v) => setF({ ...f, badges: v })} label="Breakout badges" />
            {f.badges &&
              group("Badge from", [chip("badgeMin", 3, "3×"), chip("badgeMin", 5, "5×"), chip("badgeMin", 10, "10×"), chip("badgeMin", 20, "20×")])}
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs text-ink-3">Excluded channels</p>
              <Segmented
                label="Excluded channels"
                value={f.leftOut}
                onChange={(v) => setF({ ...f, leftOut: v })}
                options={[
                  { value: "dim", label: "Dim" },
                  { value: "hide", label: "Hide" },
                ]}
              />
            </div>
            <div className="flex items-center justify-between border-t border-line pt-2 text-xs">
              <button type="button" className="text-ink-3 hover:text-ink" onClick={() => setF(NO_FILTER)}>
                Reset
              </button>
              <span className="text-ink-2">
                {shown.toLocaleString()} of {items.length.toLocaleString()} pass
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
