import { Database, Sparkles } from "lucide-react";
import { useRef, useState } from "react";

import { computeMeanings, importMaps } from "../../../api";
import { Button } from "../../../components/ui";
import { runJob, useBusy, useJobEvents } from "../../../events";
import { attempt, toast } from "../../../toasts";
import type { StoreStats } from "../../../types";

/** What the research store holds, with the two ways to grow it. */
export function StorePanel({ stats, onStats, onChanged }: { stats: StoreStats | null; onStats: (s: StoreStats) => void; onChanged: () => void }) {
  const busy = useBusy();
  const [importing, setImporting] = useState(false);
  const [note, setNote] = useState("");
  const job = useRef<string | null>(null);

  useJobEvents((e) => {
    if (e.job.id !== job.current || e.job.status === "running") return;
    job.current = null;
    const r = e.result as { read?: number; failed?: number; left?: number } | undefined;
    if (e.job.status === "done" && r)
      setNote(`Computed ${Number(r.read ?? 0).toLocaleString()} meanings${r.failed ? `, ${r.failed} failed` : ""}${r.left ? `, ${r.left.toLocaleString()} left` : ""}.`);
    onChanged();
  });

  const unread = stats ? stats.videos - (stats.videos_with_meaning ?? 0) : 0;
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-line bg-raised p-4">
      {stats ? (
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {(
            [
              ["Videos", stats.videos],
              ["Channels with videos", stats.channels_with_videos],
              ["Channels read in full", stats.channels_read_in_full],
              ["Videos searchable by meaning", stats.videos_with_meaning],
            ] as [string, number][]
          ).map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs text-ink-3">{k}</dt>
              <dd className="text-lg font-semibold text-ink">{(v ?? 0).toLocaleString()}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-sm text-ink-3">Store not read yet.</p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          icon={<Database className="size-4" />}
          disabled={importing}
          onClick={async () => {
            setImporting(true);
            const r = await attempt(importMaps());
            setImporting(false);
            if (!r) return;
            onStats(r.stats);
            toast(`Imported ${r.imported.channels.toLocaleString()} channels and ${r.imported.videos.toLocaleString()} videos`);
          }}
        >
          {importing ? "Importing" : "Import maps into the store"}
        </Button>
        <Button
          icon={<Sparkles className="size-4" />}
          disabled={busy || unread <= 0}
          title="Reads what each video is about, so videos can be searched by meaning"
          onClick={() =>
            void runJob(computeMeanings()).then((started) => {
              if (started) job.current = started.id;
            })
          }
        >
          Compute meanings{unread > 0 ? ` (${unread.toLocaleString()} left)` : ""}
        </Button>
        {note && <span className="text-xs text-ink-3">{note}</span>}
      </div>
    </div>
  );
}
