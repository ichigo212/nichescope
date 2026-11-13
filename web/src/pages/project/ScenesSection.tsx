import { Clapperboard, Lock } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { makeScenes, updateProject, updateScene } from "../../api";
import { Button, Field, TextArea } from "../../components/ui";
import { runJob } from "../../events";
import { attempt } from "../../toasts";
import type { Scene } from "../../types";
import { clock, useProject, useProjectChange } from "./context";
import { StepSection } from "./StepSection";

export function ScenesSection() {
  const { p, setP, busy } = useProject();
  const change = useProjectChange();
  const locked = p.scenes.length > 0;
  const [visual, setVisual] = useState(p.visualInstructions);
  const [prompt, setPrompt] = useState(p.promptInstructions);
  useEffect(() => {
    setVisual(p.visualInstructions);
    setPrompt(p.promptInstructions);
  }, [p.visualInstructions, p.promptInstructions]);
  const dirty = visual !== p.visualInstructions || prompt !== p.promptInstructions;

  const generate = async () => {
    if (dirty) {
      const saved = await attempt(updateProject(p.id, { visual_instructions: visual, prompt_instructions: prompt }));
      if (!saved) return;
      setP(saved);
    }
    void runJob(makeScenes(p.id));
  };

  return (
    <StepSection
      id="scenes"
      n={3}
      title="Scenes"
      done={locked}
      hint="The voiceover cut into short scenes, each with a picture to show and a prompt for its clip."
      aside={
        locked && (
          <span className="inline-flex items-center gap-1.5 text-xs text-ink-3">
            <Lock className="size-3.5" />
            Instructions locked
          </span>
        )
      }
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Visual description instructions" hint="How to describe what each scene shows.">
          <TextArea rows={3} maxLength={2000} readOnly={locked} value={visual} onChange={(e) => setVisual(e.target.value)} placeholder="For example: dark fantasy, painted look, no text on screen" />
        </Field>
        <Field label="Video prompt instructions" hint="How to write each clip's prompt.">
          <TextArea rows={3} maxLength={2000} readOnly={locked} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="For example: slow camera moves, one subject in frame" />
        </Field>
      </div>
      {!locked && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button disabled={!dirty} onClick={() => void change(updateProject(p.id, { visual_instructions: visual, prompt_instructions: prompt }))}>
            Save instructions
          </Button>
          <Button tone="primary" icon={<Clapperboard className="size-4" />} disabled={busy || !p.voiceover} onClick={() => void generate()}>
            Generate scenes
          </Button>
          {!p.voiceover && <span className="text-xs text-ink-3">Generate the voiceover first.</span>}
        </div>
      )}
      {locked && <SceneList scenes={p.scenes} />}
    </StepSection>
  );
}

function SceneList({ scenes }: { scenes: Scene[] }) {
  const [current, setCurrent] = useState(0);
  const refs = useRef<(HTMLLIElement | null)[]>([]);
  const move = (to: number) => {
    const i = Math.max(0, Math.min(scenes.length - 1, to));
    setCurrent(i);
    refs.current[i]?.focus();
  };
  return (
    <>
      <p className="mt-5 mb-2 text-xs text-ink-3">{scenes.length} scenes. Select one and use the left and right arrow keys to step through them.</p>
      <ol className="flex flex-col gap-3">
        {scenes.map((s, i) => (
          <li
            key={s.index}
            ref={(el) => {
              refs.current[i] = el;
            }}
            tabIndex={-1}
            onFocus={() => setCurrent(i)}
            onKeyDown={(e) => {
              const field = (e.target as HTMLElement).tagName === "TEXTAREA";
              if (field) return;
              if (e.key === "ArrowRight") move(i + 1);
              if (e.key === "ArrowLeft") move(i - 1);
            }}
            className={"rounded-md border bg-base/40 p-4 outline-none " + (i === current ? "border-line-strong" : "border-line")}
          >
            <SceneRow s={s} />
          </li>
        ))}
      </ol>
    </>
  );
}

function SceneRow({ s }: { s: Scene }) {
  const { p } = useProject();
  const change = useProjectChange();
  const [visual, setVisual] = useState(s.visual);
  const [prompt, setPrompt] = useState(s.prompt);
  useEffect(() => {
    setVisual(s.visual);
    setPrompt(s.prompt);
  }, [s.visual, s.prompt]);
  const dirty = visual !== s.visual || prompt !== s.prompt;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-baseline gap-3">
        <span className="shrink-0 text-xs font-semibold text-ink-3">
          #{s.index + 1} · {clock(s.start)}–{clock(s.end)}
        </span>
        <p className="min-w-0 text-sm leading-relaxed text-ink">{s.text}</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <Field label="Visual">
          <TextArea rows={3} value={visual} onChange={(e) => setVisual(e.target.value)} />
        </Field>
        <Field label="Video prompt">
          <TextArea rows={3} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        </Field>
      </div>
      {dirty && (
        <div className="flex gap-2">
          <Button tone="primary" className="h-8" onClick={() => void change(updateScene(p.id, s.index, { visual, prompt }))}>
            Save scene
          </Button>
          <Button
            tone="ghost"
            className="h-8"
            onClick={() => {
              setVisual(s.visual);
              setPrompt(s.prompt);
            }}
          >
            Discard
          </Button>
        </div>
      )}
    </div>
  );
}
