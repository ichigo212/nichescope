import { FileText, Lock } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { draftScript, updateProject } from "../../api";
import { Button, ConfirmDialog, NumberInput, TextArea } from "../../components/ui";
import { runJob } from "../../events";
import { plural } from "../../format";
import { useProject, useProjectChange, words } from "./context";
import { StepSection } from "./StepSection";

export function ScriptSection() {
  const { p, busy, draft, setDraft } = useProject();
  const change = useProjectChange();
  const [minutes, setMinutes] = useState(8);
  const [asking, setAsking] = useState(false);
  const locked = !!p.voiceover;
  const text = draft ?? p.script;
  const source = p.source;

  useEffect(() => {
    setDraft(null);
  }, [p.script, setDraft]);

  const save = () => change(updateProject(p.id, { script: text })).then((r) => r && setDraft(null));
  const writeDraft = () => void runJob(draftScript(p.id, minutes));

  return (
    <StepSection
      id="script"
      n={1}
      title="Script"
      done={!!p.script.trim()}
      hint="Everything the voiceover will say, word for word."
      aside={locked && (
        <span className="inline-flex items-center gap-1.5 text-xs text-ink-3">
          <Lock className="size-3.5" />
          Locked by the voiceover
        </span>
      )}
    >
      {source.topic && (
        <p className="mb-3 text-sm text-ink-3">
          From the topic{" "}
          {source.map_id && source.batch ? (
            <Link to={`/c/${source.map_id}/topics/${source.batch}`} className="text-ink-2 hover:text-ink hover:underline">
              {source.topic}
            </Link>
          ) : (
            <span className="text-ink-2">{source.topic}</span>
          )}
        </p>
      )}
      <TextArea
        rows={14}
        className="w-full leading-relaxed"
        readOnly={locked}
        value={text}
        onChange={(e) => setDraft(e.target.value === p.script ? null : e.target.value)}
        placeholder="Paste or write the narration"
        aria-label="Script"
      />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <span className="text-xs text-ink-3">
          {plural(words(text), "word")}
          {draft != null && <span className="ml-2 text-busy">Unsaved changes</span>}
        </span>
        {!locked && (
          <div className="flex flex-wrap items-center gap-2">
            {source.topic && (
              <>
                <label className="flex items-center gap-2 text-xs text-ink-3">
                  Minutes
                  <NumberInput className="w-20" min={1} max={60} value={minutes} onChange={(v) => setMinutes(Math.max(1, Math.min(60, Math.round(v))))} />
                </label>
                <Button icon={<FileText className="size-4" />} disabled={busy} onClick={() => (text.trim() ? setAsking(true) : writeDraft())}>
                  Write a draft
                </Button>
              </>
            )}
            <Button tone="primary" disabled={draft == null} onClick={() => void save()}>
              Save
            </Button>
          </div>
        )}
      </div>
      <ConfirmDialog
        open={asking}
        title="Replace the script?"
        body={`A ${minutes}-minute draft is written from the topic and replaces the current script${draft != null ? ", including unsaved changes" : ""}.`}
        yes="Write a draft"
        onClose={() => setAsking(false)}
        onYes={writeDraft}
      />
    </StepSection>
  );
}
