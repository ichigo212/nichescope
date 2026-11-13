import { Download, FileText, Image } from "lucide-react";
import { useState } from "react";

import { getTranscript, thumbnailUrl } from "../api";
import { Badge, Button, CopyButton, Input, Section, Switch } from "../components/ui";
import { videoId } from "../format";
import { attempt, toastError } from "../toasts";
import type { Transcript } from "../types";

const stamp = (s: number) => {
  const t = Math.floor(s);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const sec = String(t % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
};

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ToolsPage() {
  return (
    <div className="flex flex-col gap-8 page-in">
      <div>
        <h1 className="display text-[40px] text-ink">Tools</h1>
        <p className="mt-2 text-sm text-ink-3">Read a video's transcript or save its thumbnail. Paste a link or a video id.</p>
      </div>
      <TranscriptTool />
      <ThumbnailTool />
    </div>
  );
}

function TranscriptTool() {
  const [link, setLink] = useState("");
  const [reading, setReading] = useState(false);
  const [got, setGot] = useState<Transcript | null>(null);
  const [stamps, setStamps] = useState(false);
  const text = got ? (stamps ? got.segments.map((s) => `[${stamp(s.start)}] ${s.text}`).join("\n") : got.text) : "";
  const read = async () => {
    const id = videoId(link);
    if (!id) return toastError(new Error("That is not a YouTube video link"));
    setReading(true);
    const r = await attempt(getTranscript(id));
    setReading(false);
    if (r) setGot(r);
  };
  return (
    <Section title="Transcript" hint="Read once, then kept, so the second read is instant.">
      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void read();
        }}
      >
        <Input className="min-w-72 flex-1" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://www.youtube.com/watch?v=..." aria-label="Video link for the transcript" />
        <Button type="submit" tone="primary" icon={<FileText className="size-4" />} disabled={!link.trim() || reading}>
          {reading ? "Reading" : "Get transcript"}
        </Button>
      </form>
      {got && (
        <div className="mt-4 flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <p className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">{got.title}</p>
            <Badge>{got.words.toLocaleString()} words</Badge>
            <Switch checked={stamps} onChange={setStamps} label="Timestamps" />
            <CopyButton text={text} />
            <Button tone="ghost" className="h-8 px-2.5" icon={<Download className="size-4" />} onClick={() => download(`${got.video}.txt`, text)}>
              Download .txt
            </Button>
          </div>
          <pre className="max-h-[520px] overflow-y-auto rounded-md border border-line bg-base p-4 font-sans text-sm leading-relaxed whitespace-pre-wrap text-ink-2">{text}</pre>
        </div>
      )}
    </Section>
  );
}

function ThumbnailTool() {
  const [link, setLink] = useState("");
  const [shown, setShown] = useState<string | null>(null);
  const [broken, setBroken] = useState(false);
  return (
    <Section title="Thumbnail" hint="The largest version YouTube has.">
      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const id = videoId(link);
          if (!id) return toastError(new Error("That is not a YouTube video link"));
          setBroken(false);
          setShown(id);
        }}
      >
        <Input className="min-w-72 flex-1" value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://www.youtube.com/watch?v=..." aria-label="Video link for the thumbnail" />
        <Button type="submit" tone="primary" icon={<Image className="size-4" />} disabled={!link.trim()}>
          Show thumbnail
        </Button>
      </form>
      {shown && (
        <div className="mt-4 flex flex-col items-start gap-3">
          {broken ? (
            <p className="text-sm text-danger">No thumbnail found for this video.</p>
          ) : (
            <img src={thumbnailUrl(shown)} alt="Video thumbnail" onError={() => setBroken(true)} className="aspect-video w-full max-w-2xl rounded-md border border-line bg-overlay object-cover" />
          )}
          {!broken && (
            <a href={thumbnailUrl(shown)} download={`${shown}.jpg`} className="inline-flex h-9 items-center gap-2 rounded-sm border border-line-strong bg-overlay px-3.5 text-sm font-semibold text-ink hover:bg-hover">
              <Download className="size-4" />
              Download
            </a>
          )}
        </div>
      )}
    </Section>
  );
}
