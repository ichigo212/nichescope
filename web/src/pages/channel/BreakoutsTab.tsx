import { useState } from "react";

import { Empty, Segmented, Switch } from "../../components/ui";
import { VideoCard } from "../../components/VideoCard";
import { ageDays } from "../../format";
import { useMap } from "./context";

const SPANS = { "30": 30, "90": 90, all: Infinity } as const;

export function BreakoutsTab() {
  const { m } = useMap();
  const [span, setSpan] = useState<keyof typeof SPANS>("30");
  const [onNiche, setOnNiche] = useState(true);
  const inSpan = m.breakouts.filter((v) => ageDays(v.published_at) <= SPANS[span]);
  const offNiche = inSpan.filter((v) => !v.on_topic).length;
  const rows = inSpan.filter((v) => !onNiche || v.on_topic).sort((a, b) => (b.outlier ?? 0) - (a.outlier ?? 0));
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-xl font-semibold text-ink">Breaking out around {m.title}</h2>
          <p className="mt-1 text-sm text-ink-3">Videos far above their channel's usual views, biggest first.</p>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <Switch checked={onNiche} onChange={setOnNiche} label={`On-niche only${offNiche ? ` (${offNiche} hidden)` : ""}`} />
          <Segmented
            label="How recent"
            value={span}
            onChange={setSpan}
            options={[
              { value: "30", label: "30 days" },
              { value: "90", label: "90 days" },
              { value: "all", label: "All" },
            ]}
          />
        </div>
      </div>
      {rows.length ? (
        <div className="grid grid-cols-2 gap-x-4 gap-y-6 md:grid-cols-3 xl:grid-cols-4">
          {rows.map((v) => (
            <VideoCard key={`${v.channelId}-${v.id}`} v={v} />
          ))}
        </div>
      ) : (
        <Empty title="No breakouts here" body={span !== "all" ? `Nothing broke out in the last ${span} days. Show more to see older breakouts.` : "No channel on this map has a video at three times its usual."} />
      )}
    </div>
  );
}
