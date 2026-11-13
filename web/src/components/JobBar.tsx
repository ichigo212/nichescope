import { Check, TriangleAlert, X } from "lucide-react";
import { useEffect, type ReactNode } from "react";

import { dismissLast, useJobs } from "../events";
import { dismissToast, useToasts } from "../toasts";
import { Spinner } from "./ui";

/** The current job and its latest line, then how it ended. */
export function JobBar() {
  const { current, last } = useJobs();
  const finishedOk = !current && last?.status === "done";
  useEffect(() => {
    if (!finishedOk) return;
    const t = setTimeout(dismissLast, 4000);
    return () => clearTimeout(t);
  }, [finishedOk, last?.id]);

  let body: ReactNode = null;
  if (current) {
    body = (
      <div className="flex min-w-0 items-center gap-3 text-sm" aria-live="polite">
        <Spinner className="size-3.5 text-busy" />
        <span className="shrink-0 font-semibold text-ink">{current.label}</span>
        {current.message && <span className="min-w-0 truncate text-ink-3">{current.message}</span>}
      </div>
    );
  } else if (last?.status === "failed") {
    body = (
      <div role="alert" className="flex min-w-0 items-start gap-3 text-sm">
        <TriangleAlert className="mt-0.5 size-4 shrink-0 text-danger" />
        <span className="min-w-0">
          <span className="font-semibold text-ink">{last.label} failed.</span> <span className="break-words text-danger">{last.error}</span>
        </span>
        <button type="button" aria-label="Dismiss" className="ml-auto shrink-0 rounded-sm p-0.5 text-ink-3 hover:text-ink" onClick={dismissLast}>
          <X className="size-4" />
        </button>
      </div>
    );
  } else if (finishedOk && last) {
    body = (
      <div className="flex min-w-0 items-center gap-3 text-sm" aria-live="polite">
        <Check className="size-4 shrink-0 text-accent" />
        <span className="truncate text-ink-2">
          {last.label}: done
        </span>
      </div>
    );
  }
  if (!body) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-40 flex justify-center px-4 pb-4">
      <div className="pointer-events-auto w-full max-w-2xl rounded-md border border-line-strong bg-overlay px-4 py-2.5 shadow-2xl">{body}</div>
    </div>
  );
}

export function Toasts() {
  const toasts = useToasts();
  if (!toasts.length) return null;
  return (
    <ol className="fixed top-16 right-4 z-50 flex w-[min(380px,calc(100vw-32px))] flex-col gap-2">
      {toasts.map((t) => (
        <li
          key={t.id}
          role={t.tone === "error" ? "alert" : "status"}
          className={
            "flex items-start gap-3 rounded-md border px-3.5 py-2.5 text-sm shadow-xl " +
            (t.tone === "error" ? "border-danger/40 bg-[color-mix(in_srgb,var(--color-danger)_12%,var(--color-overlay))] text-ink" : "border-line-strong bg-overlay text-ink")
          }
        >
          <span className="min-w-0 flex-1 break-words">{t.text}</span>
          <button type="button" aria-label="Dismiss" className="shrink-0 rounded-sm p-0.5 text-ink-3 hover:text-ink" onClick={() => dismissToast(t.id)}>
            <X className="size-3.5" />
          </button>
        </li>
      ))}
    </ol>
  );
}
