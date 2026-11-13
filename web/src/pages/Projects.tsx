import { ChevronRight, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createProject, deleteProject, listProjects } from "../api";
import { Badge, Button, ConfirmDialog, Dialog, Empty, Field, Input, Loading, TextArea } from "../components/ui";
import { useJobEvents } from "../events";
import { ago, plural } from "../format";
import { attempt, toast } from "../toasts";
import type { ProjectStep, ProjectSummary } from "../types";

export const STEP_LABEL: Record<ProjectStep, string> = { script: "Script", scenes: "Scenes", clips: "Clips", done: "Done" };

export function ProjectsPage() {
  const [rows, setRows] = useState<ProjectSummary[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [doomed, setDoomed] = useState<ProjectSummary | null>(null);
  const load = useCallback(() => void attempt(listProjects()).then((r) => r && setRows(r.projects)), []);
  useEffect(load, [load]);
  useJobEvents((e) => e.job.status !== "running" && e.project_id && load());

  if (!rows) return <Loading />;
  return (
    <div className="flex flex-col gap-6 page-in">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="display text-[40px] text-ink">Projects</h1>
          <p className="mt-2 text-sm text-ink-3">A script becomes a voiceover, scenes, clips and a finished video.</p>
        </div>
        <Button tone="primary" icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>
          New project
        </Button>
      </div>
      {rows.length === 0 ? (
        <Empty
          title="No projects yet"
          body="Start one with a script, or use Make a video on a topic."
          action={
            <Button tone="primary" icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>
              New project
            </Button>
          }
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-line">
          <table className="w-full table-fixed text-sm">
            <thead className="bg-raised text-left text-xs text-ink-3">
              <tr>
                <th className="px-4 py-2 font-medium">Project</th>
                <th className="w-28 px-4 py-2 font-medium">Step</th>
                <th className="hidden w-40 px-4 py-2 font-medium md:table-cell">Clips</th>
                <th className="hidden w-36 px-4 py-2 font-medium sm:table-cell">Updated</th>
                <th className="w-20" />
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id} className="border-t border-line hover:bg-raised">
                  <td className="px-4 py-3">
                    <Link to={`/projects/${p.id}`} className="block truncate font-semibold text-ink hover:underline">
                      {p.title || "Untitled"}
                    </Link>
                    {p.source.topic && <span className="block truncate text-xs text-ink-3">From a topic: {p.source.topic}</span>}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={p.step === "done" ? "accent" : "plain"}>{STEP_LABEL[p.step]}</Badge>
                  </td>
                  <td className="hidden px-4 py-3 text-ink-2 md:table-cell">{p.scenes ? `${p.clips} of ${plural(p.scenes, "scene")}` : "No scenes"}</td>
                  <td className="hidden px-4 py-3 text-ink-3 sm:table-cell">{ago(p.updatedAt ?? p.createdAt)}</td>
                  <td className="pr-3">
                    <span className="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        aria-label={`Delete ${p.title}`}
                        className="inline-flex size-7 items-center justify-center rounded-sm text-ink-3 hover:bg-overlay hover:text-danger"
                        onClick={() => setDoomed(p)}
                      >
                        <Trash2 className="size-4" />
                      </button>
                      <Link to={`/projects/${p.id}`} aria-label={`Open ${p.title}`} className="text-ink-3 hover:text-ink">
                        <ChevronRight className="size-4" />
                      </Link>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <NewProject open={creating} onClose={() => setCreating(false)} />
      <ConfirmDialog
        open={!!doomed}
        title="Delete this project?"
        body={`${doomed?.title || "This project"} and its audio, clips and video are deleted. This cannot be undone.`}
        yes="Delete"
        danger
        onClose={() => setDoomed(null)}
        onYes={() => {
          const p = doomed;
          if (!p) return;
          void attempt(deleteProject(p.id)).then((ok) => {
            if (!ok) return;
            toast(`Deleted ${p.title || "the project"}`);
            load();
          });
        }}
      />
    </div>
  );
}

function NewProject({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [script, setScript] = useState("");
  const [saving, setSaving] = useState(false);
  return (
    <Dialog open={open} onClose={onClose} title="New project" wide>
      <form
        className="flex flex-col gap-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setSaving(true);
          const p = await attempt(createProject(title.trim(), script));
          setSaving(false);
          if (!p) return;
          setTitle("");
          setScript("");
          onClose();
          navigate(`/projects/${p.id}`);
        }}
      >
        <Field label="Title">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Working title" autoFocus />
        </Field>
        <Field label="Script (optional)" hint="Everything the voiceover will say, word for word. You can add it later.">
          <TextArea rows={10} value={script} onChange={(e) => setScript(e.target.value)} />
        </Field>
        <div className="flex justify-end gap-2">
          <Button tone="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" tone="primary" disabled={saving || !title.trim()}>
            Create project
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
