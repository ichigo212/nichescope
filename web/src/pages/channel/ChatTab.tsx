import { MessageCircleQuestion, Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ask } from "../../api";
import { AttachButton, AttachmentChips, useAttachments } from "../../components/Attachments";
import { Markdown } from "../../components/Markdown";
import { Avatar, Button, Spinner, TextArea } from "../../components/ui";
import { runJob, useJobEvents } from "../../events";
import { count, times, when } from "../../format";
import type { ChatMessage, Mention } from "../../types";
import { newestFirst, useMap } from "./context";
import { useVideoLookup } from "./RunPage";

const SUGGESTED = [
  "What's working lately in my niche?",
  "How are my competitors doing?",
  "How can I stand out?",
  "Which formats work best for my competitors this month?",
  "Which of my videos did best lately, and why?",
];

export function ChatTab() {
  const { m, busy } = useMap();
  const chats = newestFirst(m.chats);
  const [open, setOpen] = useState<string | null>(chats[0]?.id ?? null);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<{ job: string; question: string; before: string[] } | null>(null);
  const att = useAttachments(m.id);
  const videos = useVideoLookup();
  const chat = m.chats.find((c) => c.id === open) ?? null;
  const end = useRef<HTMLDivElement>(null);

  useJobEvents((e) => {
    if (pending && e.job.id === pending.job && e.job.status === "failed") setPending(null);
  });

  // When the answer lands, the map reloads: open the new conversation, or stay on this one.
  useEffect(() => {
    if (!pending) return;
    const fresh = m.chats.find((c) => !pending.before.includes(c.id));
    const grown = open && m.chats.find((c) => c.id === open)?.messages.some((x) => x.role === "user" && x.content === pending.question);
    if (fresh) {
      setOpen(fresh.id);
      setPending(null);
    } else if (grown) setPending(null);
  }, [m.chats, pending, open]);

  const settled = useRef(false);
  // Follow new messages, but leave the page where it is when the tab first opens.
  useEffect(() => {
    if (settled.current) end.current?.scrollIntoView({ block: "end", behavior: "smooth" });
    settled.current = true;
  }, [chat?.messages.length, pending]);

  const send = (text: string) => {
    const q = text.trim();
    if (!q) return;
    void runJob(ask(m.id, q, open, att.ids)).then((job) => {
      if (!job) return;
      setPending({ job: job.id, question: q, before: m.chats.map((c) => c.id) });
      setQuestion("");
      att.clear();
    });
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
      <nav aria-label="Conversations" className="flex flex-col gap-2">
        <Button tone={open ? "secondary" : "primary"} icon={<Plus className="size-4" />} onClick={() => setOpen(null)}>
          New conversation
        </Button>
        <ul className="flex flex-col gap-0.5 overflow-y-auto lg:max-h-[560px]">
          {chats.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                className={"w-full rounded-sm px-2.5 py-2 text-left hover:bg-overlay " + (c.id === open ? "bg-overlay" : "")}
                onClick={() => setOpen(c.id)}
              >
                <span className={"block truncate text-sm " + (c.id === open ? "text-ink" : "text-ink-2")}>{c.messages.find((x) => x.role === "user")?.content ?? "Conversation"}</span>
                <span className="block text-xs text-ink-3">{when(c.at)}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>
      <div className="flex min-w-0 flex-col gap-4">
        {!chat && !pending && (
          <div className="flex flex-col gap-3 rounded-lg border border-line bg-raised p-5">
            <p className="text-sm font-semibold text-ink">Ask about {m.title} and the channels around it</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED.map((s) => (
                <button key={s} type="button" disabled={busy} className="rounded-full border border-line-strong px-3 py-1.5 text-left text-sm text-ink-2 hover:border-ink-3 hover:text-ink disabled:opacity-40" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {chat?.messages.map((r, i) => <Message key={i} r={r} videos={videos} mapId={m.id} />)}
        {pending && (
          <>
            <div className="self-end rounded-md bg-overlay px-4 py-3 text-sm font-medium whitespace-pre-wrap text-ink sm:max-w-[80%]">{pending.question}</div>
            <p className="flex items-center gap-2 text-sm text-ink-3">
              <Spinner className="size-3.5" />
              Answering
            </p>
          </>
        )}
        <div ref={end} />
        <form
          className="flex flex-col gap-2 rounded-lg border border-line bg-raised p-3"
          onSubmit={(e) => {
            e.preventDefault();
            send(question);
          }}
        >
          <TextArea
            rows={3}
            maxLength={4000}
            className="border-transparent bg-transparent hover:border-transparent focus:border-transparent"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                send(question);
              }
            }}
            placeholder={chat ? "Ask a follow-up" : "Ask a question"}
            aria-label="Question"
          />
          <AttachmentChips files={att.files} onRemove={att.remove} />
          <div className="flex items-center justify-between gap-2">
            <AttachButton att={att} />
            <Button type="submit" tone="primary" icon={<MessageCircleQuestion className="size-4" />} disabled={busy || att.uploading || !question.trim()}>
              {chat ? "Ask follow-up" : "Ask"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Message({ r, videos, mapId }: { r: ChatMessage; videos: ReturnType<typeof useVideoLookup>; mapId: string }) {
  if (r.role === "user")
    return (
      <div className="flex flex-col gap-2 self-end rounded-md bg-overlay px-4 py-3 sm:max-w-[80%]">
        <p className="text-sm font-medium whitespace-pre-wrap text-ink">{r.content}</p>
        <AttachmentChips files={r.files} />
      </div>
    );
  return (
    <article className="flex flex-col gap-3 rounded-lg border border-line bg-raised p-5">
      <Markdown text={r.content} videos={videos} />
      {r.mentions.length > 0 && (
        <div className="flex flex-wrap gap-2 border-t border-line pt-3">
          {r.mentions.map((c) => (
            <MentionChip key={c.id} c={c} mapId={mapId} />
          ))}
        </div>
      )}
    </article>
  );
}

function MentionChip({ c, mapId }: { c: Mention; mapId: string }) {
  return (
    <Link
      to={`/c/${mapId}?channel=${encodeURIComponent(c.id)}`}
      className="flex items-center gap-2 rounded-full border border-line-strong bg-overlay py-1 pr-3 pl-1 text-xs hover:border-ink-3"
      title={`${count(c.subscribers)} subscribers · ${count(c.views30d)} views in 30 days`}
    >
      <Avatar src={c.avatar} size="size-5" />
      <span className="font-medium text-ink">{c.title}</span>
      <span className="text-ink-3">{count(c.subscribers)}</span>
      {c.breakout != null && c.breakout >= 3 && <span className="font-bold text-busy">{times(c.breakout)}</span>}
    </Link>
  );
}
