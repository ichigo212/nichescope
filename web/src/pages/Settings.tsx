import { Plug } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { connectAccount, disconnectAccount, getMcp, getStatus, setPreferences } from "../api";
import { Badge, Button, CopyButton, Loading, Section, Switch } from "../components/ui";
import { useJobEvents } from "../events";
import { count } from "../format";
import { attempt, toast } from "../toasts";
import type { McpSetup, Status } from "../types";
import { SetupSection } from "./settings/SetupSection";

export function SettingsPage() {
  const [status, setStatus] = useState<Status | null>(null);
  const load = useCallback(() => void attempt(getStatus()).then((s) => s && setStatus(s)), []);
  useEffect(load, [load]);
  useJobEvents((e) => e.job.status !== "running" && load());
  // Connecting finishes in another tab; read the accounts again on return.
  useEffect(() => {
    window.addEventListener("focus", load);
    return () => window.removeEventListener("focus", load);
  }, [load]);

  if (!status) return <Loading />;
  return (
    <div className="mx-auto flex w-full max-w-[860px] flex-col gap-5 page-in">
      <div>
        <h1 className="display text-[40px] text-ink">Settings</h1>
      </div>
      <SetupSection onChanged={load} />
      <Accounts status={status} reload={load} />
      <Section title="Quota and refresh">
        <div>
          <p className="text-sm text-ink">
            YouTube quota left today: <strong className="font-semibold">{count(status.quotaLeft)}</strong> of {count(status.quotaPerDay)}
          </p>
          <div className="mt-2 h-1.5 w-full max-w-md overflow-hidden rounded-full bg-overlay">
            <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(0, Math.min(100, (status.quotaLeft / (status.quotaPerDay || 1)) * 100))}%` }} />
          </div>
        </div>
        <div className="mt-5 border-t border-line pt-4">
          <Switch
            checked={status.preferences.auto_refresh}
            onChange={(on) =>
              void attempt(setPreferences({ auto_refresh: on })).then((p) => p && setStatus({ ...status, preferences: { ...status.preferences, auto_refresh: p.auto_refresh } }))
            }
            label="Refresh maps automatically"
            hint="While the server runs, the most overdue map is refreshed about once an hour, when quota allows."
          />
        </div>
      </Section>
      <McpPanel />
    </div>
  );
}

function Accounts({ status, reload }: { status: Status; reload: () => void }) {
  const [connecting, setConnecting] = useState(false);
  return (
    <Section
      title="Connected channels"
      hint="Connect your own channels to see their traffic and to mark the channels that really send you viewers."
      aside={
        <Button
          tone="primary"
          disabled={connecting || !status.configured.oauth}
          onClick={async () => {
            // Open the tab before the request so the browser does not block it as a popup.
            const tab = window.open("about:blank", "_blank");
            setConnecting(true);
            const r = await attempt(connectAccount());
            setConnecting(false);
            if (r && tab) tab.location.href = r.url;
            else if (r) window.open(r.url, "_blank", "noopener");
            else tab?.close();
          }}
        >
          Connect
        </Button>
      }
    >
      {!status.configured.oauth && <p className="mb-3 text-xs text-busy">Upload an OAuth client in Setup to connect a channel.</p>}
      {status.accounts.length === 0 ? (
        <p className="text-sm text-ink-3">No channel connected.</p>
      ) : (
        <ul className="flex flex-col">
          {status.accounts.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-3 border-t border-line py-2.5 text-sm first:border-t-0">
              <span className="min-w-0">
                <span className="block truncate text-ink">{a.title}</span>
                <span className="block truncate text-xs text-ink-3">{a.handle}</span>
              </span>
              <Button
                tone="ghost"
                onClick={() =>
                  void attempt(disconnectAccount(a.id)).then((r) => {
                    if (!r) return;
                    toast(`Disconnected ${a.title}`);
                    reload();
                  })
                }
              >
                Disconnect
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function CodeBlock({ label, text }: { label: string; text: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-ink">{label}</h3>
        <CopyButton text={text} />
      </div>
      <pre className="overflow-x-auto rounded-md border border-line bg-base p-3 font-mono text-xs break-all whitespace-pre-wrap text-ink-2">{text}</pre>
    </div>
  );
}

function McpPanel() {
  const [mcp, setMcp] = useState<McpSetup | null>(null);
  useEffect(() => void attempt(getMcp()).then(setMcp), []);
  return (
    <Section
      title={
        <span className="inline-flex items-center gap-2">
          <Plug className="size-4 text-ink-3" />
          MCP setup
        </span>
      }
      hint="Connect an MCP client such as Claude Desktop or Claude Code to your maps, the research store and transcripts."
      aside={<Badge tone="sync">Local</Badge>}
    >
      {!mcp ? (
        <Loading />
      ) : (
        <div className="flex flex-col gap-5">
          <CodeBlock label="Claude Code" text={mcp.claudeCode} />
          <CodeBlock label="Claude Code over HTTP (while this server runs)" text={mcp.claudeCodeHttp} />
          <CodeBlock label="Claude Desktop config" text={mcp.desktopConfig} />
          <CodeBlock label="Command (stdio)" text={[mcp.stdio.command, ...mcp.stdio.args].map((p) => (/\s/.test(p) ? `"${p}"` : p)).join(" ")} />
          <CodeBlock label="HTTP endpoint" text={mcp.http} />
        </div>
      )}
    </Section>
  );
}
