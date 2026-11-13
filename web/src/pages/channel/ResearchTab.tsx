import { useCallback, useEffect, useState } from "react";

import { storeStats } from "../../api";
import { Segmented } from "../../components/ui";
import type { StoreStats } from "../../types";
import { useMap } from "./context";
import { Finder } from "./research/Finder";
import { LiveSearch } from "./research/LiveSearch";
import { Pointers } from "./research/Pointers";
import { StorePanel } from "./research/StoreStats";

type View = "videos" | "channels" | "live" | "pointers" | "store";

export function ResearchTab() {
  const { m } = useMap();
  const [view, setView] = useState<View>("videos");
  const [stats, setStats] = useState<StoreStats | null>(null);
  const onStats = useCallback((s: StoreStats) => setStats(s), []);
  const readStats = useCallback(() => void storeStats().then(setStats, () => undefined), []);
  useEffect(readStats, [readStats]);
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-xl font-semibold text-ink">Research</h2>
          <p className="mt-1 max-w-[85ch] text-sm text-ink-3">
            Search every video and channel the maps have read
            {stats ? `: ${stats.videos.toLocaleString()} videos from ${stats.channels_with_videos.toLocaleString()} channels` : ""}.
          </p>
        </div>
        <Segmented
          label="What to research"
          value={view}
          onChange={setView}
          options={[
            { value: "videos", label: "Find videos" },
            { value: "channels", label: "Find channels" },
            { value: "live", label: "Search YouTube" },
            { value: "pointers", label: m.isOwn ? "Who sends you viewers" : "Who sends viewers" },
            { value: "store", label: "Store" },
          ]}
        />
      </div>
      {view === "videos" && <Finder key="videos" kind="videos" onStats={onStats} />}
      {view === "channels" && <Finder key="channels" kind="channels" onStats={onStats} />}
      {view === "live" && <LiveSearch />}
      {view === "pointers" && <Pointers />}
      {view === "store" && <StorePanel stats={stats} onStats={onStats} onChanged={readStats} />}
    </div>
  );
}
