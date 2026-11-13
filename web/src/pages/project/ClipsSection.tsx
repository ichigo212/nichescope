import { Film, RefreshCw } from "lucide-react";

import { makeClips, remakeClip } from "../../api";
import { Badge, Button } from "../../components/ui";
import { runJob } from "../../events";
import { plural } from "../../format";
import { clock, useProject } from "./context";
import { StepSection } from "./StepSection";

const dollars = (x: number) => `$${x < 10 ? x.toFixed(2) : Math.round(x).toLocaleString()}`;

export function ClipsSection() {
  const { p, busy } = useProject();
  const missing = p.scenes.filter((s) => !s.clip?.url).length;
  const done = p.scenes.length > 0 && missing === 0;
  const est = p.estimate;
  return (
    <StepSection id="clips" n={4} title="Clips" done={done} hint="A short video for each scene.">
      {p.scenes.length === 0 ? (
        <p className="text-sm text-ink-3">
          Generate the scenes first.
          {est.scenes > 0 && ` Expect about ${plural(est.scenes, "scene")} and about ${dollars(est.video_cost)} for ${est.clip_seconds} seconds of video.`}
        </p>
      ) : (
        <>
          {missing > 0 && (
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <Button tone="primary" icon={<Film className="size-4" />} disabled={busy} onClick={() => void runJob(makeClips(p.id))}>
                {missing === p.scenes.length ? "Generate all clips" : `Generate ${plural(missing, "missing clip")}`}
              </Button>
              <span className="text-sm text-ink-3">
                About {dollars(est.video_cost)} for {est.clip_seconds} seconds of video{missing < p.scenes.length ? " across every scene" : ""}.
              </span>
            </div>
          )}
          <ol className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {p.scenes.map((s) => (
              <li key={s.index} className="flex min-w-0 flex-col gap-2">
                <div className="aspect-video w-full overflow-hidden rounded-md bg-overlay">
                  {s.clip?.url ? (
                    <video controls preload="metadata" src={s.clip.url} className="size-full object-cover" />
                  ) : (
                    <div className="grid size-full place-items-center p-3 text-center text-xs">
                      {s.clip?.error ? <span className="text-danger">{s.clip.error}</span> : <span className="text-ink-3">No clip yet</span>}
                    </div>
                  )}
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-ink-3">
                    #{s.index + 1} · {clock(s.start)}–{clock(s.end)} · {s.clipSeconds}s clip
                  </span>
                  {s.clip && (
                    <Button tone="ghost" className="h-7 px-2 text-xs" icon={<RefreshCw className="size-3.5" />} disabled={busy} onClick={() => void runJob(remakeClip(p.id, s.index))}>
                      Regenerate
                    </Button>
                  )}
                </div>
                {s.clip?.speech && (
                  <span>
                    <Badge tone="busy">Speech detected · muted in the video</Badge>
                  </span>
                )}
              </li>
            ))}
          </ol>
        </>
      )}
    </StepSection>
  );
}
