import { createContext, useCallback, useContext } from "react";

import { attempt } from "../../toasts";
import type { Project } from "../../types";

export interface ProjectCtx {
  p: Project;
  setP: (p: Project) => void;
  voices: Record<string, string>;
  busy: boolean;
  /** script text not yet saved, or null when the saved script is current */
  draft: string | null;
  setDraft: (text: string | null) => void;
}

export const ProjectContext = createContext<ProjectCtx | null>(null);

export function useProject(): ProjectCtx {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProject outside a project page");
  return ctx;
}

/** Run a request that answers with the updated project, and show it. */
export function useProjectChange() {
  const { setP } = useProject();
  return useCallback(
    async (request: Promise<Project>) => {
      const p = await attempt(request);
      if (p) setP(p);
      return p;
    },
    [setP],
  );
}

export const clock = (seconds: number) => {
  const t = Math.max(0, Math.round(seconds));
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
};

export const words = (text: string) => text.split(/\s+/).filter(Boolean).length;
