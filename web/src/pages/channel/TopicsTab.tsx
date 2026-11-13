import { ChevronRight, Paperclip, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { removeSaved, updateSaved } from "../../api";
import { Button, Empty, Segmented, TextArea } from "../../components/ui";
import { VideoChip } from "../../components/VideoCard";
import { plural, when } from "../../format";
import type { SavedStatus, SavedTopic } from "../../types";
import { newestFirst, useMap, useMapChange } from "./context";

const STATUSES: { value: SavedStatus; label: string }[] = [
  { value: "planned", label: "Planned" },
  { value: "working", label: "Working on" },
  { value: "done", label: "Done" },
];

export function TopicsTab({ onGenerate }: { onGenerate: () => void }) {
  const { m, busy } = useMap();
  const [view, setView] = useState<"runs" | "saved">("runs");
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Segmented
          label="Topics"
          value={view}
          onChange={setView}
          options={[
            { value: "runs", label: `Runs (${m.batches.length})` },
            { value: "saved", label: `Saved topics (${m.savedTopics.length})` },
          ]}
        />
        <Button tone="primary" icon={<Sparkles className="size-4" />} disabled={busy} onClick={onGenerate}>
          Generate topics
        </Button>
      </div>
      {view === "runs" ? <Runs onGenerate={onGenerate} /> : <Saved />}
    </div>
  );
}

function Runs({ onGenerate }: { onGenerate: () => void }) {
  const { m, busy } = useMap();
  const navigate = useNavigate();
  const rows = newestFirst(m.batches);
  if (!rows.length)
    return (
      <Empty
        title="No topics yet"
        body="Generate topics to get video ideas drawn from what is breaking out around this channel."
        action={
          <Button tone="primary" icon={<Sparkles className="size-4" />} disabled={busy} onClick={onGenerate}>
            Generate topics
          </Button>
        }
      />
    );
  return (
    <div className="overflow-hidden rounded-lg border border-line">
      <table className="w-full table-fixed text-sm">
        <thead className="bg-raised text-left text-xs text-ink-3">
          <tr>
            <th className="w-52 px-4 py-2 font-medium">Date</th>
            <th className="px-4 py-2 font-medium">Run</th>
            <th className="hidden w-48 px-4 py-2 font-medium md:table-cell">Learned from</th>
            <th className="w-10" />
          </tr>
        </thead>
        <tbody>
          {rows.map((b) => (
            <tr key={b.id} className="cursor-pointer border-t border-line hover:bg-raised" onClick={() => navigate(`/c/${m.id}/topics/${b.id}`)}>
              <td className="px-4 py-3 font-semibold text-ink">{when(b.at)}</td>
              <td className="px-4 py-3">
                <span className="block truncate text-ink-2">{b.instructions || plural(b.topics.length, "topic")}</span>
                <span className="flex items-center gap-2 text-xs text-ink-3">
                  {b.instructions && plural(b.topics.length, "topic")}
                  {b.followups.length > 0 && <span>{plural(b.followups.filter((f) => f.role === "user").length, "follow-up")}</span>}
                  {b.files.length > 0 && (
                    <span className="inline-flex items-center gap-1">
                      <Paperclip className="size-3" />
                      {b.files.length}
                    </span>
                  )}
                </span>
              </td>
              <td className="hidden px-4 py-3 text-ink-3 md:table-cell">{b.learnedFrom ? plural(b.learnedFrom, "channel") : "This map"}</td>
              <td className="pr-3 text-ink-3">
                <ChevronRight className="size-4" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Saved() {
  const { m } = useMap();
  const [filter, setFilter] = useState<SavedStatus | "all">("all");
  if (!m.savedTopics.length) return <Empty title="No saved topics" body="Save a topic from a run and it stays here with its titles and evidence." />;
  const rows = m.savedTopics.filter((s) => filter === "all" || s.status === filter);
  return (
    <div className="flex flex-col gap-4">
      <Segmented
        label="Which saved topics"
        value={filter}
        onChange={setFilter}
        options={[
          { value: "all", label: `All (${m.savedTopics.length})` },
          ...STATUSES.map((s) => ({ value: s.value, label: `${s.label} (${m.savedTopics.filter((t) => t.status === s.value).length})` })),
        ]}
      />
      {rows.length === 0 ? <p className="text-sm text-ink-3">Nothing here.</p> : rows.map((s) => <SavedCard key={s.id} s={s} />)}
    </div>
  );
}

function SavedCard({ s }: { s: SavedTopic }) {
  const { m } = useMap();
  const change = useMapChange();
  const [note, setNote] = useState(s.note);
  return (
    <article className="flex flex-col gap-3 rounded-lg border border-line bg-raised p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="text-base leading-snug font-semibold text-ink">{s.topic}</h3>
          <p className="mt-0.5 text-xs text-ink-3">Saved {when(s.at)}</p>
        </div>
        <div className="flex items-center gap-2">
          <Segmented<SavedStatus> label={`Status of ${s.topic}`} value={s.status} onChange={(status) => void change(updateSaved(m.id, s.id, { status }))} options={STATUSES} />
          <Button tone="ghost" aria-label={`Remove ${s.topic}`} icon={<X className="size-4" />} onClick={() => void change(removeSaved(m.id, s.id))} />
        </div>
      </div>
      {s.why && <p className="max-w-[80ch] text-sm leading-relaxed text-ink-2">{s.why}</p>}
      {s.titles.length > 0 && (
        <fieldset className="flex flex-col gap-1">
          <legend className="mb-1 text-xs font-semibold text-ink-3">Title to use</legend>
          {s.titles.map((x) => (
            <label key={x} className="flex items-start gap-2 text-sm text-ink">
              <input type="radio" className="mt-1 accent-[var(--color-accent)]" name={`title-${s.id}`} checked={s.title === x} onChange={() => void change(updateSaved(m.id, s.id, { title: x }))} />
              <span>{x}</span>
            </label>
          ))}
        </fieldset>
      )}
      {s.evidence.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {s.evidence.slice(0, 4).map((v) => (
            <VideoChip key={v.id} v={v} />
          ))}
        </div>
      )}
      <TextArea
        className="min-h-12"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        onBlur={() => note !== s.note && void change(updateSaved(m.id, s.id, { note }))}
        placeholder="Notes"
        aria-label={`Notes on ${s.topic}`}
      />
    </article>
  );
}
