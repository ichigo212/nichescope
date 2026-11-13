import { AudioLines } from "lucide-react";
import { useState } from "react";

import { makeVoiceover, updateProject } from "../../api";
import { Button, ConfirmDialog, Field, Select } from "../../components/ui";
import { runJob } from "../../events";
import { attempt } from "../../toasts";
import { clock, useProject, useProjectChange } from "./context";
import { StepSection } from "./StepSection";

export function VoiceSection() {
  const { p, setP, voices, busy, draft, setDraft } = useProject();
  const change = useProjectChange();
  const [asking, setAsking] = useState(false);
  const locked = !!p.voiceover;
  const script = draft ?? p.script;
  const options = Object.entries(voices).map(([name, about]): [string, string] => [name, about ? `${name} — ${about}` : name]);
  if (!(p.voice in voices)) options.unshift([p.voice, p.voice]);

  const generate = async () => {
    if (draft != null) {
      const saved = await attempt(updateProject(p.id, { script: draft }));
      if (!saved) return;
      setP(saved);
      setDraft(null);
    }
    void runJob(makeVoiceover(p.id));
  };

  return (
    <StepSection id="voiceover" n={2} title="Voiceover" done={locked} hint={locked ? undefined : "The script read aloud. Scenes are timed to it."}>
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Voice" className="min-w-64 flex-1">
          <Select label="Voice" value={p.voice} options={options} onChange={(voice) => void change(updateProject(p.id, { voice }))} disabled={locked} />
        </Field>
        {!locked && (
          <Button tone="primary" icon={<AudioLines className="size-4" />} disabled={busy || !script.trim()} onClick={() => setAsking(true)}>
            Generate audio
          </Button>
        )}
      </div>
      {!locked && !script.trim() && <p className="mt-2 text-xs text-ink-3">Write the script first.</p>}
      {p.voiceover && (
        <div className="mt-4 flex flex-col gap-2">
          <audio controls preload="metadata" src={p.voiceover.url} className="w-full" />
          <p className="text-xs text-ink-3">{clock(p.voiceover.seconds)} long</p>
        </div>
      )}
      <ConfirmDialog
        open={asking}
        title="Generate audio?"
        body={
          <>
            <p>Generating it locks the script and voice.</p>
            {draft != null && <p className="mt-2 text-busy">The script has unsaved changes. They are saved first.</p>}
            {p.estimate.voice_seconds > 0 && <p className="mt-2 text-ink-3">About {clock(p.estimate.voice_seconds)} of audio.</p>}
          </>
        }
        yes="Generate audio"
        onClose={() => setAsking(false)}
        onYes={() => void generate()}
      />
    </StepSection>
  );
}
