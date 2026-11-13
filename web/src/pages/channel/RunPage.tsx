import { ArrowLeft, Bookmark, Check, Clapperboard, MessageCircleQuestion, ThumbsDown, ThumbsUp, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { followUp, projectFromTopic, saveTopic, setMark, youtubeVideo } from "../../api";
import { AttachButton, AttachmentChips, useAttachments } from "../../components/Attachments";
import { Markdown, type VideoLookup } from "../../components/Markdown";
import { Button, CopyButton, Empty, TextArea, buttonClass } from "../../components/ui";
import { VideoChip } from "../../components/VideoCard";
import { runJob } from "../../events";
import { ago, count, plural, when } from "../../format";
import type { Batch, FollowUp, Topic } from "../../types";
import { attempt } from "../../toasts";
import { useMap, useMapChange } from "./context";

export function useVideoLookup(): VideoLookup {
  const { m } = useMap();
  return useMemo(() => {
    const all: VideoLookup = new Map();
    m.breakouts.forEach((v) => all.set(v.id, v));
    m.channels.forEach((c) => c.breakouts.forEach((v) => all.set(v.id, v)));
    m.own?.videos.forEach((v) => all.set(v.id, v));
    m.uploads.recent.forEach((v) => all.set(v.id, v));
    m.uploads.popular.forEach((v) => all.set(v.id, v));
    return all;
  }, [m]);
}

export function RunPage({ runId, onGenerate }: { runId: string; onGenerate: () => void }) {
  const { m } = useMap();
  const videos = useVideoLookup();
  const batch = m.batches.find((b) => b.id === runId);
  const back = (
    <Link to={`/c/${m.id}/topics`} className={buttonClass("ghost", "self-start")}>
      <ArrowLeft className="size-4" />
      All runs
    </Link>
  );
  if (!batch)
    return (
      <div className="flex flex-col gap-4">
        {back}
        <Empty title="This run is not on the map" body="It may have been made before the map was restored." action={<Button onClick={onGenerate}>Generate topics</Button>} />
      </div>
    );
  const flagged = batch.topics.filter((t) => t.onYoutube).length;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        {back}
        <div>
          <h2 className="text-xl font-semibold text-ink">Topics from {when(batch.at)}</h2>
          <p className="mt-1 text-sm text-ink-3">
            {plural(batch.topics.length, "topic")}
            {batch.learnedFrom ? ` · learned from ${plural(batch.learnedFrom, "channel")}` : ""}
            {flagged > 0 && <span className="text-busy"> · {flagged} may already be on YouTube, listed last</span>}
          </p>
          {batch.instructions && (
            <p className="mt-3 max-w-[80ch] rounded-md border border-line bg-raised px-3 py-2 text-sm text-ink-2">
              <span className="text-ink-3">Instructions: </span>
              {batch.instructions}
            </p>
          )}
          {batch.searched && (
            <p className="mt-2 text-sm text-ink-2">
              Searched for <strong className="font-semibold text-ink">{batch.searched.subject}</strong>:{" "}
              {plural(batch.searched.onMap, "video")} from this map, {plural(batch.searched.onYoutube, "video")} from YouTube search
              {batch.searched.queries.length > 0 && <span className="text-ink-3"> ({batch.searched.queries.map((q) => `"${q}"`).join(", ")})</span>}
            </p>
          )}
        </div>
        <AttachmentChips files={batch.files} />
      </div>
      {batch.analysis && (
        <section className="rounded-lg border border-line bg-raised p-5">
          <h3 className="mb-3 text-sm font-semibold text-ink">Analysis</h3>
          <Markdown text={batch.analysis} videos={videos} />
        </section>
      )}
      <div className="flex flex-col gap-4">
        {batch.topics.map((t, i) => (
          <TopicCard key={`${batch.id}-${t.topic}`} t={t} n={i + 1} batch={batch} />
        ))}
      </div>
      <Thread batch={batch} videos={videos} />
      <AskForMore batch={batch} />
    </div>
  );
}

function MarkButtons({ value, onSet, label }: { value: string | undefined; onSet: (v: "like" | "no" | null) => void; label: string }) {
  const cls = "rounded-sm p-1.5 hover:bg-overlay ";
  return (
    <span className="inline-flex shrink-0 items-center gap-0.5">
      <button type="button" aria-label={`Like ${label}`} aria-pressed={value === "like"} className={cls + (value === "like" ? "text-accent" : "text-ink-3")} onClick={() => onSet(value === "like" ? null : "like")}>
        <ThumbsUp className="size-3.5" />
      </button>
      <button type="button" aria-label={`Reject ${label}`} aria-pressed={value === "no"} className={cls + (value === "no" ? "text-danger" : "text-ink-3")} onClick={() => onSet(value === "no" ? null : "no")}>
        <ThumbsDown className="size-3.5" />
      </button>
    </span>
  );
}

function topicText(t: Topic, n: number) {
  const lines = [`#${n} ${t.topic}`, "", t.why];
  if (t.detail) lines.push("", t.detail);
  if (t.titles.length) lines.push("", "Titles:", ...t.titles.map((x) => `- ${x}`));
  return lines.join("\n").trim();
}

const REASONS: [keyof Topic["reasons"], string][] = [
  ["proven", "Proven demand"],
  ["gap", "Gap"],
  ["angle", "Angle"],
  ["risk", "Risk"],
];

function TopicCard({ t, n, batch }: { t: Topic; n: number; batch: Batch }) {
  const { m } = useMap();
  const change = useMapChange();
  const navigate = useNavigate();
  const [making, setMaking] = useState(false);
  const saved = m.savedTopics.some((s) => s.topic === t.topic);
  const reasons = REASONS.filter(([k]) => t.reasons[k]);
  const close = t.closestOwn;
  const fitTone = t.fit == null ? "" : t.fit >= 7 ? "bg-accent/15 text-accent" : t.fit >= 5 ? "bg-sync/15 text-sync" : "bg-overlay text-ink-2";
  return (
    <article className={"flex flex-col gap-4 rounded-lg border bg-raised p-5 " + (m.marks.topics[t.topic] === "no" ? "border-line opacity-60" : "border-line")}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-baseline gap-3">
          <span className="shrink-0 text-sm font-semibold text-ink-3">#{n}</span>
          <h3 className="min-w-0 text-lg leading-snug font-semibold text-ink">{t.topic}</h3>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <MarkButtons label={t.topic} value={m.marks.topics[t.topic]} onSet={(v) => void change(setMark(m.id, "topics", t.topic, v))} />
          <CopyButton text={topicText(t, n)} label="Copy topic" />
          <Button
            className="h-8"
            icon={<Clapperboard className="size-4" />}
            disabled={making}
            onClick={async () => {
              setMaking(true);
              const p = await attempt(projectFromTopic(m.id, batch.id, t.topic));
              setMaking(false);
              if (p) navigate(`/projects/${p.id}`);
            }}
          >
            Make a video
          </Button>
          <Button
            tone={saved ? "secondary" : "primary"}
            className="h-8"
            disabled={saved}
            icon={saved ? <Check className="size-4" /> : <Bookmark className="size-4" />}
            onClick={() => void change(saveTopic(m.id, batch.id, t.topic))}
          >
            {saved ? "Saved" : "Save"}
          </Button>
        </div>
      </header>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-ink-3">
        {t.fit != null && (
          <span className={"rounded-[4px] px-1.5 py-px font-semibold " + fitTone} title="How well it fits this channel">
            Fit {t.fit}/10
          </span>
        )}
        {t.name && (t.name.source && t.name.video ? (
          <a className="hover:text-ink hover:underline" href={`https://www.youtube.com/watch?v=${t.name.video}`} target="_blank" rel="noreferrer">
            “{t.name.name}” is named in {t.name.source}
          </a>
        ) : (
          <span className="text-busy" title="No cited video's title, description or comments contain this name">
            “{t.name.name}” not confirmed: check the name
          </span>
        ))}
        {t.expectedViews && (
          <span title="From this channel's usual views up to what the cited breakouts did against their own channels">
            Expected {count(t.expectedViews.low)}–{count(t.expectedViews.high)} views
          </span>
        )}
        <span>
          From {plural(t.evidence.length + t.evidenceLost, "video")} on {plural(new Set(t.evidence.map((v) => v.channel)).size, "channel")}
          {t.evidence.some((v) => v.searched) && `, ${t.evidence.filter((v) => v.searched).length} found by searching`}
        </span>
        {t.evidenceLost > 0 && <span className="text-busy">{t.evidenceLost} no longer on the map</span>}
      </div>
      {t.onYoutube && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-busy/30 bg-busy/5 px-3 py-2 text-sm">
          <TriangleAlert className="size-4 shrink-0 text-busy" />
          <span className="font-semibold text-ink">{t.onYoutube.mine ? "You may have made this already" : "May already be on YouTube"}</span>
          <a href={youtubeVideo(t.onYoutube.video)} target="_blank" rel="noreferrer noopener" className="min-w-0 truncate text-ink-2 hover:text-ink hover:underline">
            {t.onYoutube.title}
          </a>
          <span className="text-xs text-ink-3">
            {t.onYoutube.mine ? "" : `${t.onYoutube.channel} · `}
            {count(t.onYoutube.views)} views{t.onYoutube.days != null ? ` · ${Math.round(t.onYoutube.days)} days ago` : ""}
          </span>
        </div>
      )}
      {t.why && <p className="max-w-[80ch] text-sm leading-relaxed text-ink-2">{t.why}</p>}
      {t.titles.length > 0 && (
        <ul className="flex flex-col divide-y divide-line border-y border-line">
          {t.titles.map((x) => (
            <li key={x} className={"flex items-center justify-between gap-3 py-1.5 " + (m.marks.titles[x] === "no" ? "opacity-50" : "")}>
              <span className="min-w-0 text-sm text-ink">{x}</span>
              <span className="flex shrink-0 items-center">
                <CopyButton text={x} />
                <MarkButtons label={x} value={m.marks.titles[x]} onSet={(v) => void change(setMark(m.id, "titles", x, v))} />
              </span>
            </li>
          ))}
        </ul>
      )}
      {t.detail && (
        <details className="group">
          <summary className="text-sm font-medium text-ink-2 select-none hover:text-ink">Detailed topic</summary>
          <Markdown text={t.detail} className="mt-2" />
        </details>
      )}
      {reasons.length > 0 && (
        <details className="group">
          <summary className="text-sm font-medium text-ink-2 select-none hover:text-ink">Why this topic</summary>
          <dl className="mt-2 grid gap-3 sm:grid-cols-2">
            {reasons.map(([k, label]) => (
              <div key={k} className="rounded-md bg-overlay px-3 py-2">
                <dt className={"text-xs font-semibold " + (k === "risk" ? "text-busy" : "text-ink-3")}>{label}</dt>
                <dd className="mt-0.5 text-sm leading-relaxed text-ink-2">{t.reasons[k]}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
      {t.evidence.length > 0 && (
        <div className="flex flex-col gap-2">
          <h4 className="text-xs font-semibold text-ink-3">Evidence</h4>
          <div className="flex flex-wrap gap-2">
            {t.evidence.map((v) => (
              <VideoChip key={v.id} v={v} />
            ))}
          </div>
        </div>
      )}
      {close && (
        <p className="text-xs leading-relaxed text-ink-3">
          Closest video of yours:{" "}
          <a href={youtubeVideo(close.id)} target="_blank" rel="noreferrer noopener" className="text-ink-2 hover:text-ink hover:underline">
            {close.title}
          </a>
          {` · ${count(close.period_views ?? close.views)} views`}
          {close.avg_view_pct != null && ` · ${close.avg_view_pct}% watched`}
          {close.published_at && ` · ${ago(close.published_at)}`}
        </p>
      )}
    </article>
  );
}

function Thread({ batch, videos }: { batch: Batch; videos: VideoLookup }) {
  if (!batch.followups.length) return null;
  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-sm font-semibold text-ink-2">Follow-ups</h3>
      {batch.followups.map((f, i) => (
        <FollowUpMessage key={i} f={f} videos={videos} />
      ))}
    </section>
  );
}

function FollowUpMessage({ f, videos }: { f: FollowUp; videos: VideoLookup }) {
  if (f.role === "user")
    return (
      <div className="flex flex-col gap-2 self-end rounded-md bg-overlay px-4 py-3 sm:max-w-[80%]">
        <p className="text-sm font-medium whitespace-pre-wrap text-ink">{f.content}</p>
        <AttachmentChips files={f.files} />
      </div>
    );
  return (
    <div className="flex flex-col gap-2 rounded-md border border-line bg-raised p-4">
      {f.content && <Markdown text={f.content} videos={videos} />}
      <div className="flex flex-wrap gap-2 text-xs">
        {f.addedTopics > 0 && <span className="rounded-full bg-accent/15 px-2 py-px font-semibold text-accent">Added {plural(f.addedTopics, "topic")}</span>}
        {f.titlesFor.length > 0 && (
          <span className="rounded-full bg-sync/15 px-2 py-px font-semibold text-sync">Titles added to {f.titlesFor.map((n) => `#${n}`).join(", ")}</span>
        )}
      </div>
    </div>
  );
}

function AskForMore({ batch }: { batch: Batch }) {
  const { m, busy } = useMap();
  const [text, setText] = useState("");
  const att = useAttachments(m.id);
  const n = batch.topics.length;
  const chips = [
    n >= 2 && "5 more topics like #2",
    n >= 1 && "More titles for #1",
    n >= 3 && "Shorter titles for #3",
    n >= 4 && "Why would #4 work?",
  ].filter((c): c is string => !!c);
  return (
    <form
      className="flex flex-col gap-3 rounded-lg border border-line bg-raised p-4"
      onSubmit={(e) => {
        e.preventDefault();
        void runJob(followUp(m.id, batch.id, text.trim(), att.ids)).then((job) => {
          if (!job) return;
          setText("");
          att.clear();
        });
      }}
    >
      <div>
        <p className="text-sm font-semibold text-ink">Ask for more</p>
        <p className="text-xs text-ink-3">More topics in a direction, more titles for one, or why one would work. Refer to topics by number.</p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {chips.map((c) => (
          <button key={c} type="button" className="rounded-full border border-line-strong px-2.5 py-1 text-xs text-ink-2 hover:border-ink-3 hover:text-ink" onClick={() => setText(c)}>
            {c}
          </button>
        ))}
      </div>
      <TextArea rows={2} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask about these topics" aria-label="Ask for more" />
      <AttachmentChips files={att.files} onRemove={att.remove} />
      <div className="flex items-center justify-between gap-2">
        <AttachButton att={att} />
        <Button type="submit" tone="primary" icon={<MessageCircleQuestion className="size-4" />} disabled={busy || att.uploading || !text.trim()}>
          Send
        </Button>
      </div>
    </form>
  );
}

