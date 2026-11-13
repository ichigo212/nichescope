import { Check } from "lucide-react";
import type { ReactNode } from "react";

export const STEPS: [string, string][] = [
  ["script", "Script"],
  ["voiceover", "Voiceover"],
  ["scenes", "Scenes"],
  ["clips", "Clips"],
  ["video", "Video"],
];

export function StepSection({
  id,
  n,
  title,
  hint,
  done,
  aside,
  children,
}: {
  id: string;
  n: number;
  title: string;
  hint?: ReactNode;
  done: boolean;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-20 rounded-lg border border-line bg-raised p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span
            className={
              "mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-bold " +
              (done ? "bg-accent text-accent-ink" : "bg-overlay text-ink-2")
            }
          >
            {done ? <Check className="size-3.5" /> : n}
          </span>
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-ink">{title}</h2>
            {hint && <p className="mt-0.5 text-sm text-ink-3">{hint}</p>}
          </div>
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function Stepper({ done }: { done: Record<string, boolean> }) {
  const current = STEPS.find(([id]) => !done[id])?.[0];
  return (
    <ol className="flex flex-wrap items-center gap-1 text-sm">
      {STEPS.map(([id, label], i) => (
        <li key={id} className="flex items-center gap-1">
          {i > 0 && <span className="h-px w-5 bg-line-strong" />}
          <a
            href={`#${id}`}
            className={
              "inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-medium " +
              (done[id] ? "text-accent hover:bg-overlay" : id === current ? "bg-overlay text-ink" : "text-ink-3 hover:text-ink-2")
            }
          >
            {done[id] && <Check className="size-3.5" />}
            {label}
          </a>
        </li>
      ))}
    </ol>
  );
}
