import { Sparkles } from "lucide-react";
import { useState } from "react";

import { generateTopics } from "../../api";
import { AttachButton, AttachmentChips, useAttachments } from "../../components/Attachments";
import { Button, Dialog, TextArea } from "../../components/ui";
import { runJob } from "../../events";
import type { Job } from "../../types";
import { useMap } from "./context";

export function GenerateDialog({ open, onClose, onStarted }: { open: boolean; onClose: () => void; onStarted: (job: Job) => void }) {
  const { m, busy } = useMap();
  const [instructions, setInstructions] = useState("");
  const att = useAttachments(m.id);
  const st = m.settings;
  return (
    <Dialog open={open} onClose={onClose} title="Generate topics">
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          void runJob(generateTopics(m.id, instructions.trim(), att.ids)).then((job) => {
            if (!job) return;
            setInstructions("");
            att.clear();
            onStarted(job);
            onClose();
          });
        }}
      >
        <p className="text-sm text-ink-3">
          {st.topics} topics with {st.titles} titles each, from this map's breakouts. Change the counts in Settings.
          {st.instructions ? " Standing instructions are added." : ""}
        </p>
        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-semibold text-ink-2">Instructions for this run (optional)</span>
          <TextArea
            rows={4}
            maxLength={m.limits.instructions}
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            placeholder="For example: only stories with a female lead, nothing longer than 40 minutes"
          />
        </label>
        <AttachmentChips files={att.files} onRemove={att.remove} />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <AttachButton att={att} />
          <div className="flex gap-2">
            <Button tone="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" tone="primary" icon={<Sparkles className="size-4" />} disabled={busy || att.uploading}>
              Generate topics
            </Button>
          </div>
        </div>
        {busy && <p className="text-xs text-busy">Another job is running. Wait for it to finish.</p>}
      </form>
    </Dialog>
  );
}
