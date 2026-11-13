import { Download, Film } from "lucide-react";
import { useEffect, useState } from "react";

import { renderVideo, updateProject } from "../../api";
import { Button, Field, Slider, Spinner } from "../../components/ui";
import { runJob } from "../../events";
import { useProject, useProjectChange } from "./context";
import { StepSection } from "./StepSection";

export function VideoSection() {
  const { p, busy } = useProject();
  const change = useProjectChange();
  const [sound, setSound] = useState(p.clipSound);
  useEffect(() => {
    setSound(p.clipSound);
  }, [p.clipSound]);
  useEffect(() => {
    if (sound === p.clipSound) return;
    const t = setTimeout(() => void change(updateProject(p.id, { clip_sound: sound })), 500);
    return () => clearTimeout(t);
  }, [sound, p.clipSound, p.id, change]);

  const ready = p.scenes.length > 0 && p.scenes.every((s) => s.clip?.url);
  const r = p.render;
  return (
    <StepSection id="video" n={5} title="Video" done={r?.status === "done"} hint="The voiceover over the clips, as one video.">
      <Field label={`Clip sound: ${sound}`} hint="The clips' own sound under the voice. 0 leaves it out." className="max-w-md">
        <Slider label="Clip sound" min={0} max={100} value={sound} onChange={setSound} />
      </Field>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button tone="primary" icon={<Film className="size-4" />} disabled={busy || !ready || r?.status === "rendering"} onClick={() => void runJob(renderVideo(p.id))}>
          {r?.status === "done" ? "Render again" : "Render video"}
        </Button>
        {!ready && <span className="text-xs text-ink-3">Every scene needs a clip first.</span>}
        {r?.status === "rendering" && (
          <span className="flex items-center gap-2 text-sm text-busy">
            <Spinner className="size-3.5" />
            Rendering
          </span>
        )}
      </div>
      {r?.status === "failed" && <pre className="mt-3 max-h-48 overflow-auto rounded-md border border-danger/40 bg-danger/10 p-3 font-mono text-xs whitespace-pre-wrap text-danger">{r.error ?? "The render failed."}</pre>}
      {r?.status === "done" && r.url && (
        <div className="mt-4 flex flex-col items-start gap-3">
          <video controls preload="metadata" src={r.url} className="aspect-video w-full max-w-3xl rounded-md bg-black" />
          <a href={r.url} download={`${p.title || p.id}.mp4`} className="inline-flex h-9 items-center gap-2 rounded-sm border border-line-strong bg-overlay px-3.5 text-sm font-semibold text-ink hover:bg-hover">
            <Download className="size-4" />
            Download video
          </a>
        </div>
      )}
    </StepSection>
  );
}
