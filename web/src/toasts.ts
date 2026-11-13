import { useSyncExternalStore } from "react";

export interface Toast {
  id: number;
  text: string;
  tone: "error" | "info";
}

let toasts: Toast[] = [];
let next = 1;
const watchers = new Set<() => void>();

function publish(list: Toast[]) {
  toasts = list;
  watchers.forEach((w) => w());
}

export function dismissToast(id: number) {
  publish(toasts.filter((t) => t.id !== id));
}

export function toast(text: string, tone: Toast["tone"] = "info") {
  const id = next++;
  publish([...toasts.slice(-3), { id, text, tone }]);
  setTimeout(() => dismissToast(id), tone === "error" ? 8000 : 3500);
}

export function toastError(e: unknown) {
  toast(e instanceof Error ? e.message : String(e), "error");
}

export function useToasts(): Toast[] {
  return useSyncExternalStore(
    (fn) => {
      watchers.add(fn);
      return () => void watchers.delete(fn);
    },
    () => toasts,
  );
}

/** Await a request; on failure show why and resolve to null. */
export async function attempt<T>(request: Promise<T>): Promise<T | null> {
  try {
    return await request;
  } catch (e) {
    toastError(e);
    return null;
  }
}
