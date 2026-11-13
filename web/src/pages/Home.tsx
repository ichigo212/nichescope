import { Plus, Trash2, TriangleAlert, Undo2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { checkChannel, createMap, getHome, getStatus, removeMap, restoreMap } from "../api";
import { ChannelPicker } from "../components/ChannelPicker";
import { MiniMap } from "../components/MiniMap";
import { Avatar, Badge, Button, Empty, Loading, Select, Spinner } from "../components/ui";
import { VideoCard } from "../components/VideoCard";
import { runJob, useBusy, useJobEvents } from "../events";
import { ago, count, plural } from "../format";
import { attempt, toast } from "../toasts";
import type { Card, ChannelCheck, Home } from "../types";

const STEPS: [string, string][] = [
  ["0", "This channel only"],
  ["1", "1 step out"],
  ["2", "2 steps out"],
  ["3", "3 steps out"],
  ["4", "4 steps out"],
  ["5", "5 steps out"],
];

export function HomePage() {
  const [home, setHome] = useState<Home | null>(null);
  const busy = useBusy();
  const load = useCallback(() => void attempt(getHome()).then((h) => h && setHome(h)), []);
  useEffect(load, [load]);
  useJobEvents((e) => e.job.status === "done" && load());
  const [noModel, setNoModel] = useState(false);
  useEffect(() => {
    void getStatus().then((s) => setNoModel(!s.configured.model), () => undefined);
  }, []);

  if (!home) return <Loading />;
  return (
    <div className="flex flex-col gap-12 page-in">
      <section className="flex flex-col gap-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="display text-[40px] text-ink">Channels</h1>
            <p className="mt-2 text-sm text-ink-3">Each map holds a channel and the channels YouTube shows beside it.</p>
          </div>
        </div>
        {noModel && (
          <p className="flex flex-wrap items-center gap-2 rounded-md border border-busy/30 bg-busy/5 px-3 py-2 text-sm text-ink-2">
            Add a Gemini key in Settings to generate topics and answers.
            <Link to="/settings" className="font-semibold text-sync hover:underline">
              Open Settings
            </Link>
          </p>
        )}
        <AddChannel busy={busy} known={home.cards} />
        {home.cards.length === 0 ? (
          <Empty title="No channel mapped yet" body="Add a channel above. Its competitors are found from what YouTube recommends beside its videos." />
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-3">
            {home.cards.map((c) => (
              <ChannelCard key={c.id} c={c} onRemoved={load} />
            ))}
          </div>
        )}
      </section>

      {home.breakouts.length > 0 && (
        <section className="flex flex-col gap-4">
          <div>
            <h2 className="text-xl font-semibold text-ink">Breaking out</h2>
            <p className="mt-1 text-sm text-ink-3">Recent videos far above their channel's usual views, across every map.</p>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-6 md:grid-cols-3 xl:grid-cols-4">
            {home.breakouts.map((v) => (
              <VideoCard key={v.id} v={v} />
            ))}
          </div>
        </section>
      )}

      {home.removedMaps.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold text-ink-2">Removed maps</h2>
          <ul className="flex flex-col">
            {home.removedMaps.map((r) => (
              <li key={r.file} className="flex items-center gap-3 border-t border-line py-2 text-sm">
                <Avatar src={r.avatar} />
                <span className="min-w-0 flex-1 truncate text-ink-2">
                  {r.title}
                  <span className="ml-2 text-xs text-ink-3">removed {ago(r.at)}</span>
                </span>
                <Button
                  tone="ghost"
                  icon={<Undo2 className="size-4" />}
                  onClick={() =>
                    void attempt(restoreMap(r.file)).then((ok) => {
                      if (ok) {
                        toast(`Restored ${r.title}`);
                        load();
                      }
                    })
                  }
                >
                  Restore
                </Button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function AddChannel({ busy, known }: { busy: boolean; known: Card[] }) {
  const navigate = useNavigate();
  const [steps, setSteps] = useState("1");
  const [checking, setChecking] = useState(false);
  const [small, setSmall] = useState<ChannelCheck | null>(null);

  const map = (channel: string) => {
    setSmall(null);
    void runJob(createMap(channel, Number(steps)));
  };
  const check = async (channel: string) => {
    setChecking(true);
    setSmall(null);
    const got = await attempt(checkChannel(channel));
    setChecking(false);
    if (!got) return;
    if (got.mapped || known.some((c) => c.id === got.id)) {
      navigate(`/c/${got.id}`);
      return;
    }
    if (got.small) setSmall(got);
    else map(got.id);
  };

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-line bg-raised p-4">
      <div className="flex flex-wrap items-center gap-2">
        <ChannelPicker
          className="min-w-72 flex-1"
          label="Channel name, link or @handle"
          action="Add a channel"
          actionIcon={checking ? <Spinner className="size-3.5" /> : <Plus className="size-4" />}
          disabled={busy || checking}
          onPick={(channel) => void check(channel)}
        />
        <Select label="How far out to map" value={steps} options={STEPS} onChange={setSteps} />
      </div>
      <p className="text-xs text-ink-3">Each step out reads the neighbours of the channels found so far. More steps take longer.</p>
      {small && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-md border border-busy/40 bg-busy/10 px-3 py-2.5 text-sm">
          <TriangleAlert className="size-4 shrink-0 text-busy" />
          <Avatar src={small.avatar} size="size-6" />
          <p className="min-w-0 flex-1 text-ink-2">
            <span className="font-semibold text-ink">{small.title}</span> ({count(small.subscribers)} subscribers, {plural(small.videos, "video")}). This channel is just
            starting out. Its recommendations are mostly noise; map a larger competitor instead.
          </p>
          <div className="flex gap-2">
            <Button tone="ghost" onClick={() => setSmall(null)}>
              Cancel
            </Button>
            <Button disabled={busy} onClick={() => map(small.id)}>
              Map anyway
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function ChannelCard({ c, onRemoved }: { c: Card; onRemoved: () => void }) {
  const [sure, setSure] = useState(false);
  useEffect(() => {
    if (!sure) return;
    const t = setTimeout(() => setSure(false), 4000);
    return () => clearTimeout(t);
  }, [sure]);
  return (
    <div className="group relative flex flex-col gap-3 rounded-lg border border-line bg-raised p-3 transition-colors hover:border-line-strong">
      <button
        type="button"
        aria-label={sure ? `Confirm removing ${c.title}` : `Remove ${c.title}`}
        title={sure ? "Click again to remove. The map is kept and can be restored." : "Remove"}
        className={
          "absolute top-2 right-2 z-10 inline-flex size-7 items-center justify-center rounded-sm hover:bg-overlay " + (sure ? "text-danger" : "text-ink-3 hover:text-danger")
        }
        onClick={() => {
          if (!sure) return setSure(true);
          setSure(false);
          void attempt(removeMap(c.id)).then((ok) => {
            if (ok) {
              toast(`Removed ${c.title}`);
              onRemoved();
            }
          });
        }}
      >
        <Trash2 className="size-4" />
      </button>
      <Link to={`/c/${c.id}`} className="flex flex-col items-center gap-3">
        <MiniMap c={c} />
        <span className="w-full min-w-0">
          <span className="flex items-center gap-2">
            <span className="truncate font-semibold text-ink group-hover:underline">{c.title}</span>
            {c.isOwn && <Badge tone="accent">Your channel</Badge>}
          </span>
          <span className="block truncate text-xs text-ink-3">
            {c.handle || "No handle"} · {count(c.subscribers)} subscribers
          </span>
          <span className="mt-1.5 block text-sm text-ink-2">
            <strong className="font-semibold text-ink">{c.near}</strong> channels around it
          </span>
          <span className="block text-xs text-ink-3">Updated {ago(c.scannedAt)}</span>
        </span>
      </Link>
      {sure && <p className="text-xs text-danger">Click the bin again to remove {c.title}. The map is kept and can be restored.</p>}
      <Link to={`/c/${c.id}`} className="inline-flex h-9 items-center justify-center rounded-sm border border-line-strong bg-overlay text-sm font-semibold text-ink hover:bg-hover">
        Open
      </Link>
    </div>
  );
}
