import { Check, ExternalLink, FileUp, PlugZap, X } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { checkSetup, getSetup, removeVertexKey, updateSetup, uploadOauthClient, uploadVertexKey } from "../../api";
import { Badge, Button, Field, Input, Loading, OutLink, Section, Segmented, Spinner } from "../../components/ui";
import { attempt, toast } from "../../toasts";
import type { CheckResult, SetupCheck, SetupModelKey, SetupStatus } from "../../types";

const MODEL_FIELDS: [SetupModelKey, string][] = [
  ["GEMINI_MODEL", "Model"],
  ["GEMINI_LIGHT_MODEL", "Light model"],
  ["GEMINI_EMBED_MODEL", "Embedding model"],
  ["GEMINI_TTS_MODEL", "Voice model"],
  ["VERTEX_LOCATION", "Vertex AI location"],
  ["VIDEO_MODEL", "Video model"],
  ["VIDEO_LOCATION", "Video location"],
  ["VIDEO_PRICE_PER_SECOND", "Video price per second (USD)"],
];

const capital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Keys, credential files and model choices, with what each one makes possible. */
export function SetupSection({ onChanged }: { onChanged: () => void }) {
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  useEffect(() => {
    void attempt(getSetup()).then((s) => s && setSetup(s));
  }, []);
  const apply = async (request: Promise<SetupStatus>, done?: string) => {
    const s = await attempt(request);
    if (!s) return false;
    setSetup(s);
    onChanged();
    if (done) toast(done);
    return true;
  };

  if (!setup) return <Section title="Setup"><Loading /></Section>;
  const ready: [string, boolean][] = [
    ["Model", setup.ready.model],
    ["YouTube", setup.ready.youtube],
    ["Video clips", setup.ready.video],
    ["Analytics", setup.ready.analytics],
  ];
  return (
    <Section title="Setup" hint="Everything Nichescope needs to reach Google. Keys are stored in this installation's .env file.">
      <ul className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {ready.map(([label, ok]) => (
          <li key={label} className="flex items-center gap-2 rounded-md bg-overlay px-3 py-2 text-sm">
            {ok ? <Check className="size-4 shrink-0 text-accent" /> : <X className="size-4 shrink-0 text-ink-3" />}
            <span className="min-w-0">
              <span className="block text-ink">{label}</span>
              <span className={"block text-xs " + (ok ? "text-accent" : "text-ink-3")}>{ok ? "Ready" : "Not set up"}</span>
            </span>
          </li>
        ))}
      </ul>
      <div className="flex flex-col divide-y divide-line">
        <Part title="Language model">
          <SecretField
            label="Gemini API key"
            masked={setup.geminiApiKey}
            onSave={(v) => apply(updateSetup({ GEMINI_API_KEY: v }), "Gemini API key saved")}
            onRemove={() => apply(updateSetup({ GEMINI_API_KEY: "" }), "Gemini API key removed")}
          />
          <OutLink href="https://aistudio.google.com/apikey" className="inline-flex items-center gap-1.5 self-start text-xs text-sync hover:underline">
            Get a Gemini API key
            <ExternalLink className="size-3" />
          </OutLink>
          <div className="mt-2 flex flex-col gap-2">
            <p className="text-sm text-ink-2">Or Vertex AI</p>
            <div className="flex flex-wrap items-center gap-2">
              {setup.vertex ? (
                <>
                  <Badge tone="accent">Project {setup.vertex.project ?? "unknown"}</Badge>
                  <Button tone="ghost" className="h-8" onClick={() => void apply(removeVertexKey(), "Vertex AI key removed")}>
                    Remove
                  </Button>
                </>
              ) : (
                <FileButton label="Upload service-account key (.json)" onFile={(f) => apply(uploadVertexKey(f), "Vertex AI key saved")} />
              )}
            </div>
            <p className="text-xs text-ink-3">Video clips need Vertex AI.</p>
          </div>
        </Part>

        <Part title="YouTube">
          <Segmented
            label="How to read YouTube"
            value={setup.youtubeSource}
            onChange={(v) => void apply(updateSetup({ YOUTUBE_SOURCE: v }))}
            options={[
              { value: "public", label: "Public pages (no quota, rounded numbers)" },
              { value: "api", label: "YouTube Data API (exact numbers, uses quota)" },
            ]}
          />
          {setup.youtubeSource === "public" ? (
            <p className="text-xs text-ink-3">Maps and research read YouTube's public pages. Nothing counts against your API quota.</p>
          ) : (
            <SecretField
              label="YouTube Data API key"
              masked={setup.youtubeApiKey}
              onSave={(v) => apply(updateSetup({ YOUTUBE_API_KEY: v }), "YouTube API key saved")}
              onRemove={() => apply(updateSetup({ YOUTUBE_API_KEY: "" }), "YouTube API key removed")}
            />
          )}
        </Part>

        <Part title="OAuth client">
          <div className="flex flex-wrap items-center gap-2">
            {setup.oauthClient && <Badge tone="accent">Uploaded</Badge>}
            <FileButton label={setup.oauthClient ? "Replace OAuth client (.json)" : "OAuth client (.json)"} onFile={(f) => apply(uploadOauthClient(f), "OAuth client saved")} />
          </div>
          <p className="text-xs leading-relaxed text-ink-3">
            Needed before you can connect a channel. Google Cloud → APIs &amp; Services → Credentials → Create OAuth client → Desktop app.
            <br />
            Enable YouTube Data API v3 and YouTube Analytics API.
          </p>
        </Part>

        <Advanced setup={setup} onSave={(values) => apply(updateSetup(values), "Advanced settings saved")} />
        <TestConnection />
      </div>
    </Section>
  );
}

function Part({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 py-5 first:pt-0 last:pb-0">
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      {children}
    </div>
  );
}

function SecretField({ label, masked, onSave, onRemove }: { label: string; masked: string | null; onSave: (v: string) => Promise<boolean>; onRemove: () => Promise<boolean> }) {
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  const run = async (fn: () => Promise<boolean>) => {
    setSaving(true);
    const ok = await fn();
    setSaving(false);
    if (ok) setValue("");
  };
  return (
    <form
      className="flex flex-col gap-1.5"
      onSubmit={(e) => {
        e.preventDefault();
        if (value.trim()) void run(() => onSave(value.trim()));
      }}
    >
      <span className="text-xs font-semibold text-ink-2">
        {label}
        {masked && <span className="ml-2 font-normal text-accent">{capital(masked)}</span>}
      </span>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          type="password"
          autoComplete="off"
          className="min-w-64 flex-1"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={masked ? "Paste a new key to replace it" : "Paste the key"}
          aria-label={label}
        />
        <Button type="submit" tone="primary" disabled={saving || !value.trim()}>
          Save
        </Button>
        {masked && (
          <Button tone="ghost" disabled={saving} onClick={() => void run(onRemove)}>
            Remove
          </Button>
        )}
      </div>
    </form>
  );
}

function FileButton({ label, onFile }: { label: string; onFile: (f: File) => Promise<boolean> }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  return (
    <>
      <input
        ref={input}
        type="file"
        accept=".json,application/json"
        className="hidden"
        onChange={async (e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (!f) return;
          setBusy(true);
          await onFile(f);
          setBusy(false);
        }}
      />
      <Button icon={busy ? <Spinner className="size-3.5" /> : <FileUp className="size-4" />} disabled={busy} onClick={() => input.current?.click()}>
        {label}
      </Button>
    </>
  );
}

function Advanced({ setup, onSave }: { setup: SetupStatus; onSave: (values: Record<string, string>) => Promise<boolean> }) {
  const [values, setValues] = useState<Record<string, string>>(setup.models);
  useEffect(() => {
    setValues(setup.models);
  }, [setup.models]);
  const changed = Object.fromEntries(Object.entries(values).filter(([k, v]) => v !== setup.models[k as SetupModelKey]));
  const dirty = Object.keys(changed).length > 0;
  return (
    <details className="group py-5 last:pb-0">
      <summary className="text-sm font-semibold text-ink select-none">Advanced</summary>
      <form
        className="mt-3 flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          void onSave(changed);
        }}
      >
        <div className="grid gap-3 sm:grid-cols-2">
          {MODEL_FIELDS.map(([key, label]) => (
            <Field key={key} label={label}>
              <Input value={values[key] ?? ""} onChange={(e) => setValues((all) => ({ ...all, [key]: e.target.value }))} placeholder={key} />
            </Field>
          ))}
        </div>
        <div>
          <Button type="submit" tone="primary" disabled={!dirty}>
            Save
          </Button>
        </div>
      </form>
    </details>
  );
}

function TestConnection() {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<SetupCheck | null>(null);
  const rows: [string, CheckResult | undefined][] = result
    ? [
        ["Model", result.model],
        ["YouTube", result.youtube],
        ["Video clips", result.video],
      ]
    : [];
  return (
    <div className="flex flex-col gap-3 py-5 last:pb-0">
      <div>
        <Button
          icon={testing ? <Spinner className="size-3.5" /> : <PlugZap className="size-4" />}
          disabled={testing}
          onClick={async () => {
            setTesting(true);
            setResult(await attempt(checkSetup()));
            setTesting(false);
          }}
        >
          {testing ? "Testing" : "Test connection"}
        </Button>
      </div>
      {rows.length > 0 && (
        <ul className="flex flex-col gap-1.5 text-sm">
          {rows
            .filter((r): r is [string, CheckResult] => !!r[1])
            .map(([label, r]) => (
              <li key={label} className="flex items-start gap-2">
                {r.ok ? <Check className="mt-0.5 size-4 shrink-0 text-accent" /> : <X className="mt-0.5 size-4 shrink-0 text-danger" />}
                <span className="min-w-0">
                  <span className="text-ink">{label}</span>{" "}
                  {r.ok ? <span className="text-accent">OK</span> : <span className="break-words text-danger">{r.error ?? "Failed"}</span>}
                </span>
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
