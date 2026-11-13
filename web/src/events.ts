import { useEffect, useRef, useSyncExternalStore } from "react";

import { toastError } from "./toasts";
import type { Job, JobEvent, Status } from "./types";

interface JobState {
  current: Job | null;
  /** the latest job to finish, until dismissed */
  last: Job | null;
}

let state: JobState = { current: null, last: null };
const watchers = new Set<() => void>();
const listeners = new Set<(e: JobEvent) => void>();
let source: EventSource | null = null;
let listening = false;

function set(next: Partial<JobState>) {
  state = { ...state, ...next };
  watchers.forEach((w) => w());
}

function emit(e: JobEvent) {
  const { job } = e;
  if (job.status === "running") set({ current: job });
  else set({ current: state.current?.id === job.id ? null : state.current, last: job });
  listeners.forEach((fn) => fn(e));
}

function hello(status: Status) {
  const before = state.current;
  if (status.job) {
    set({ current: status.job });
    return;
  }
  // A job that finished while the stream was down: tell the pages so they refetch.
  if (before && before.status === "running") {
    const finished = status.recentJobs.find((j) => j.id === before.id) ?? { ...before, status: "done" as const };
    emit({ type: "job", job: finished, map_id: finished.map_id ?? undefined });
  }
}

/** Open the one event stream the app listens on. The browser reconnects it by itself.
 *  It is closed when the page is left: a stream left open by every page load would use up
 *  the browser's six connections to the app and stall the next page. */
export function startEvents() {
  if (source) return;
  if (!listening) {
    listening = true;
    window.addEventListener("pagehide", () => {
      source?.close();
      source = null;
    });
    window.addEventListener("pageshow", (e) => {
      if (e.persisted) startEvents();
    });
  }
  source = new EventSource("/api/events");
  source.onmessage = (msg: MessageEvent<string>) => {
    let data: { type?: string; status?: Status; job?: Job };
    try {
      data = JSON.parse(msg.data);
    } catch {
      return;
    }
    if (data.type === "hello" && data.status) hello(data.status);
    else if (data.type === "job" && data.job) emit(data as JobEvent);
  };
}

/** A job a POST just started, before its first event arrives. */
export function noteStarted(job: Job) {
  if (state.current?.id !== job.id) set({ current: job });
}

export function dismissLast() {
  set({ last: null });
}

export function useJobs(): JobState {
  return useSyncExternalStore(
    (fn) => {
      watchers.add(fn);
      return () => void watchers.delete(fn);
    },
    () => state,
  );
}

/** True while any job runs: only one runs at a time, so job buttons wait. */
export function useBusy(): boolean {
  return useJobs().current?.status === "running";
}

/** Hear every job event. The handler may change between renders. */
export function useJobEvents(handler: (e: JobEvent) => void) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const fn = (e: JobEvent) => ref.current(e);
    listeners.add(fn);
    return () => void listeners.delete(fn);
  }, []);
}

/** Map id a finished event is about: the job's own, or the one its result named. */
export function eventMapId(e: JobEvent): string | null {
  return e.map_id ?? e.job.map_id ?? null;
}

/** Start a job from a POST that answers {job}. Errors (409 busy and others) become toasts. */
export async function runJob(started: Promise<{ job: Job }>): Promise<Job | null> {
  try {
    const { job } = await started;
    noteStarted(job);
    return job;
  } catch (e) {
    toastError(e);
    return null;
  }
}
