import { ArrowLeft, MessageCircleQuestion, RefreshCw, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, useNavigate, useParams } from "react-router-dom";

import { ApiError, getMap, refreshMap } from "../api";
import { Avatar, Badge, Button, Empty, Loading, buttonClass } from "../components/ui";
import { eventMapId, runJob, useBusy, useJobEvents } from "../events";
import { ago, count } from "../format";
import { toastError } from "../toasts";
import type { Job, NicheMap } from "../types";
import { BreakoutsTab } from "./channel/BreakoutsTab";
import { ChannelsTab } from "./channel/ChannelsTab";
import { ChatTab } from "./channel/ChatTab";
import { MapContext, newestFirst, type MapCtx } from "./channel/context";
import { GenerateDialog } from "./channel/GenerateDialog";
import { OwnTab } from "./channel/OwnTab";
import { ResearchTab } from "./channel/ResearchTab";
import { RunPage } from "./channel/RunPage";
import { SettingsTab } from "./channel/SettingsTab";
import { StudyTab } from "./channel/StudyTab";
import { TopicsTab } from "./channel/TopicsTab";

type Tab = "channels" | "topics" | "breakouts" | "research" | "study" | "yours" | "chat" | "settings";
const TABS: Tab[] = ["channels", "topics", "breakouts", "research", "study", "yours", "chat", "settings"];

export function ChannelPage() {
  const { id = "", tab: rawTab, run } = useParams();
  const navigate = useNavigate();
  const [m, setM] = useState<NicheMap | null>(null);
  const [missing, setMissing] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const topicsJob = useRef<string | null>(null);
  const busy = useBusy();
  const tab: Tab = run ? "topics" : TABS.includes(rawTab as Tab) ? (rawTab as Tab) : "channels";

  const reload = useCallback(async () => {
    try {
      const got = await getMap(id);
      setM(got);
      setMissing(null);
      return got;
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setMissing(e.message);
      else toastError(e);
      return null;
    }
  }, [id]);

  useEffect(() => {
    setM(null);
    void reload();
  }, [reload]);

  useJobEvents((e) => {
    if (e.job.status === "running" || eventMapId(e) !== id) return;
    void reload().then((fresh) => {
      if (fresh && e.job.id === topicsJob.current && e.job.status === "done") {
        topicsJob.current = null;
        const newest = newestFirst(fresh.batches)[0];
        if (newest) navigate(`/c/${id}/topics/${newest.id}`);
      }
    });
  });

  const ctx = useMemo<MapCtx | null>(() => (m ? { m, setM, reload, busy } : null), [m, reload, busy]);

  if (missing)
    return (
      <Empty
        title="This map is not here"
        body={missing}
        action={
          <Link to="/" className={buttonClass("secondary")}>
            Back to channels
          </Link>
        }
      />
    );
  if (!m || !ctx) return <Loading />;

  const yours = m.isOwn && !!m.own;
  const tabs: [Tab, string][] = [
    ["channels", "Channels"],
    ["topics", "Topics"],
    ["breakouts", "Breakouts"],
    ["research", "Research"],
    ["study", "Study"],
    ...(yours ? ([["yours", "Your channel"]] as [Tab, string][]) : []),
    ["chat", "Chat"],
    ["settings", "Settings"],
  ];
  const onTopicsStarted = (job: Job) => {
    topicsJob.current = job.id;
  };

  return (
    <MapContext.Provider value={ctx}>
      <div className="flex flex-col gap-6 page-in">
        <header className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex min-w-0 items-center gap-3">
              <Link to="/" aria-label="All channels" className="rounded-sm p-1.5 text-ink-3 hover:bg-hover hover:text-ink">
                <ArrowLeft className="size-5" />
              </Link>
              <Avatar src={m.avatar} size="size-11" />
              <div className="min-w-0">
                <h1 className="flex items-center gap-2 truncate text-xl leading-tight font-semibold text-ink">
                  {m.title}
                  {m.isOwn && <Badge tone="accent">Your channel</Badge>}
                </h1>
                <p className="truncate text-xs text-ink-3">
                  {m.handle || "No handle"} · {count(m.subscribers)} subscribers · updated {ago(m.scannedAt)}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button icon={<RefreshCw className="size-4" />} disabled={busy} onClick={() => void runJob(refreshMap(m.id))}>
                Refresh
              </Button>
              <Button icon={<MessageCircleQuestion className="size-4" />} onClick={() => navigate(`/c/${m.id}/chat`)}>
                Ask
              </Button>
              <Button tone="primary" icon={<Sparkles className="size-4" />} disabled={busy} onClick={() => setGenerating(true)}>
                Generate topics
              </Button>
            </div>
          </div>
          <nav role="tablist" aria-label="Sections" className="flex flex-wrap gap-1 border-b border-line">
            {tabs.map(([value, label]) => (
              <NavLink
                key={value}
                role="tab"
                aria-selected={tab === value}
                to={value === "channels" ? `/c/${m.id}` : `/c/${m.id}/${value}`}
                className={
                  "-mb-px flex h-10 items-center border-b-2 px-3 text-sm font-medium transition-colors duration-150 " +
                  (tab === value ? "border-accent text-ink" : "border-transparent text-ink-3 hover:text-ink-2")
                }
              >
                {label}
              </NavLink>
            ))}
          </nav>
        </header>
        {m.ownError && (
          <p role="alert" className="rounded-md border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
            Your channel's analytics could not be read: {m.ownError}
          </p>
        )}
        {run ? (
          <RunPage runId={run} onGenerate={() => setGenerating(true)} />
        ) : (
          <>
            {tab === "channels" && <ChannelsTab />}
            {tab === "topics" && <TopicsTab onGenerate={() => setGenerating(true)} />}
            {tab === "breakouts" && <BreakoutsTab />}
            {tab === "research" && <ResearchTab />}
            {tab === "study" && <StudyTab />}
            {tab === "yours" && (yours ? <OwnTab /> : <Empty title="No analytics for this channel" body="Connect this channel in Settings to see its traffic." />)}
            {tab === "chat" && <ChatTab />}
            {tab === "settings" && <SettingsTab />}
          </>
        )}
      </div>
      <GenerateDialog open={generating} onClose={() => setGenerating(false)} onStarted={onTopicsStarted} />
    </MapContext.Provider>
  );
}
