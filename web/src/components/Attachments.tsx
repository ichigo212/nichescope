import { FileText, Paperclip, X } from "lucide-react";
import { useRef, useState } from "react";

import { uploadFile } from "../api";
import { toastError } from "../toasts";
import type { Attachment } from "../types";
import { Button, Spinner } from "./ui";

export const MAX_FILES = 4;
const ACCEPT = ".png,.jpg,.jpeg,.webp,.pdf,.docx,.txt,.md,.csv";

/** Files picked for a request: each is uploaded as it is picked, and sent by id. */
export function useAttachments(mapId: string) {
  const [files, setFiles] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(0);
  const add = async (list: FileList | null) => {
    const room = MAX_FILES - files.length;
    const picked = Array.from(list ?? []).slice(0, Math.max(0, room));
    if (list && list.length > room) toastError(new Error(`Attach ${MAX_FILES} files at most`));
    setUploading((n) => n + picked.length);
    for (const f of picked) {
      try {
        const got = await uploadFile(mapId, f);
        setFiles((all) => [...all, got].slice(0, MAX_FILES));
      } catch (e) {
        toastError(e);
      } finally {
        setUploading((n) => n - 1);
      }
    }
  };
  return {
    files,
    ids: files.map((f) => f.id),
    uploading: uploading > 0,
    add,
    remove: (id: string) => setFiles((all) => all.filter((f) => f.id !== id)),
    clear: () => setFiles([]),
  };
}

export function AttachButton({ att, disabled }: { att: ReturnType<typeof useAttachments>; disabled?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          void att.add(e.target.files);
          e.target.value = "";
        }}
      />
      <Button
        tone="ghost"
        icon={att.uploading ? <Spinner className="size-3.5" /> : <Paperclip className="size-4" />}
        disabled={disabled || att.files.length >= MAX_FILES}
        onClick={() => input.current?.click()}
        title="Images, PDF, .docx or text files, up to 4"
      >
        Attach
      </Button>
    </>
  );
}

export function AttachmentChips({ files, onRemove }: { files: Attachment[]; onRemove?: (id: string) => void }) {
  if (!files.length) return null;
  return (
    <ul className="flex flex-wrap gap-2">
      {files.map((f) => (
        <li key={f.id} className="flex max-w-60 items-center gap-1.5 rounded-sm border border-line bg-overlay py-1 pr-1.5 pl-2 text-xs text-ink-2">
          {f.kind === "image" && f.url ? (
            <img src={f.url} alt="" className="size-5 rounded-[3px] object-cover" />
          ) : (
            <FileText className="size-3.5 shrink-0 text-ink-3" />
          )}
          {f.url ? (
            <a href={f.url} target="_blank" rel="noreferrer noopener" className="truncate hover:text-ink">
              {f.name}
            </a>
          ) : (
            <span className="truncate">{f.name}</span>
          )}
          {onRemove && (
            <button type="button" aria-label={`Remove ${f.name}`} className="rounded-sm p-0.5 text-ink-3 hover:text-ink" onClick={() => onRemove(f.id)}>
              <X className="size-3" />
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
