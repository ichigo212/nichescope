import { ArrowLeft, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError, deleteProject, getProject, listProjects, updateProject } from "../api";
import { Button, ConfirmDialog, Empty, Loading, buttonClass } from "../components/ui";
import { useBusy, useJobEvents } from "../events";
import { ago } from "../format";
import { attempt, toast, toastError } from "../toasts";
import type { Project } from "../types";
import { ClipsSection } from "./project/ClipsSection";
import { ProjectContext, type ProjectCtx } from "./project/context";
import { ScenesSection } from "./project/ScenesSection";
import { ScriptSection } from "./project/ScriptSection";
import { Stepper } from "./project/StepSection";
import { VideoSection } from "./project/VideoSection";
import { VoiceSection } from "./project/VoiceSection";

export function ProjectPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const busy = useBusy();
  const [p, setP] = useState<Project | null>(null);
  const [missing, setMissing] = useState<string | null>(null);
  const [voices, setVoices] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [deleting, setDeleting] = useState(false);

  const reload = useCallback(async () => {
    try {
      const got = await getProject(id);
      setP(got);
      setMissing(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setMissing(e.message);
      else toastError(e);
    }
  }, [id]);

  useEffect(() => {
    setP(null);
    void reload();
  }, [reload]);
  useEffect(() => {
    void attempt(listProjects()).then((r) => r && setVoices(r.voices));
  }, []);
  const savedTitle = p?.title;
  useEffect(() => {
    if (savedTitle != null) setTitle(savedTitle);
  }, [savedTitle]);
  useJobEvents((e) => {
    if (e.job.status !== "running" && e.project_id === id) void reload();
  });

  const ctx = useMemo<ProjectCtx | null>(() => (p ? { p, setP, voices, busy, draft, setDraft } : null), [p, voices, busy, draft]);

  if (missing)
    return (
      <Empty
        title="This project is not here"
        body={missing}
        action={
          <Link to="/projects" className={buttonClass("secondary")}>
            Back to projects
          </Link>
        }
      />
    );
  if (!p || !ctx) return <Loading />;

  const done = {
    script: !!p.script.trim(),
    voiceover: !!p.voiceover,
    scenes: p.scenes.length > 0,
    clips: p.scenes.length > 0 && p.scenes.every((s) => s.clip?.url),
    video: p.render?.status === "done",
  };
  const saveTitle = () => {
    const t = title.trim();
    if (!t || t === p.title) return setTitle(p.title);
    void attempt(updateProject(p.id, { title: t })).then((r) => r && setP(r));
  };

  return (
    <ProjectContext.Provider value={ctx}>
      <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-5 page-in">
        <header className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <Link to="/projects" aria-label="All projects" className="rounded-sm p-1.5 text-ink-3 hover:bg-hover hover:text-ink">
                <ArrowLeft className="size-5" />
              </Link>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                onBlur={saveTitle}
                onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
                aria-label="Project title"
                className="min-w-0 flex-1 rounded-sm border border-transparent bg-transparent px-2 py-1 text-xl font-semibold text-ink hover:border-line-strong focus:border-accent focus:outline-none"
              />
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-ink-3">Updated {ago(p.updatedAt ?? p.createdAt)}</span>
              <Button tone="ghost" icon={<Trash2 className="size-4" />} onClick={() => setDeleting(true)}>
                Delete
              </Button>
            </div>
          </div>
          <Stepper done={done} />
        </header>
        <ScriptSection />
        <VoiceSection />
        <ScenesSection />
        <ClipsSection />
        <VideoSection />
      </div>
      <ConfirmDialog
        open={deleting}
        title="Delete this project?"
        body={`${p.title || "This project"} and its audio, clips and video are deleted. This cannot be undone.`}
        yes="Delete"
        danger
        onClose={() => setDeleting(false)}
        onYes={() =>
          void attempt(deleteProject(p.id)).then((ok) => {
            if (!ok) return;
            toast(`Deleted ${p.title || "the project"}`);
            navigate("/projects");
          })
        }
      />
    </ProjectContext.Provider>
  );
}
