import type {
  Attachment,
  ChannelCheck,
  ChannelSuggestion,
  FoundChannels,
  FoundVideos,
  Home,
  Job,
  LiveResults,
  McpSetup,
  Mesh,
  NicheMap,
  Pointer,
  Project,
  ProjectSummary,
  SavedStatus,
  SetupCheck,
  SetupStatus,
  Status,
  StoreStats,
  Transcript,
  Account,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

type Body = Record<string, unknown> | FormData | undefined;

async function request<T>(method: string, path: string, body?: Body): Promise<T> {
  const init: RequestInit = { method, headers: { Accept: "application/json" } };
  if (body instanceof FormData) init.body = body;
  else if (body !== undefined) {
    init.body = JSON.stringify(body);
    init.headers = { ...init.headers, "Content-Type": "application/json" };
  }
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("Could not reach Nichescope. Is the server running?", 0);
  }
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    throw new ApiError(detail(data) ?? `${res.status} ${res.statusText}`, res.status);
  }
  return data as T;
}

function detail(data: unknown): string | null {
  if (!data || typeof data !== "object" || !("detail" in data)) return null;
  const d = (data as { detail: unknown }).detail;
  if (typeof d === "string") return d;
  // FastAPI validation errors arrive as a list of {loc, msg}
  if (Array.isArray(d)) {
    return d
      .map((e) => {
        const row = e as { loc?: unknown[]; msg?: string };
        const field = (row.loc ?? []).filter((x) => x !== "body").join(" ");
        return field ? `${field}: ${row.msg ?? ""}` : (row.msg ?? "");
      })
      .join("; ");
  }
  return JSON.stringify(d);
}

const get = <T>(path: string) => request<T>("GET", path);
const post = <T>(path: string, body?: Body) => request<T>("POST", path, body ?? {});
const put = <T>(path: string, body: Body) => request<T>("PUT", path, body);
const patch = <T>(path: string, body: Body) => request<T>("PATCH", path, body);
const del = <T>(path: string) => request<T>("DELETE", path);
const enc = encodeURIComponent;
const mapPath = (id: string) => `/api/maps/${enc(id)}`;

export type Started = { job: Job };

// system
export const getStatus = () => get<Status>("/api/status");
export const getHome = () => get<Home>("/api/home");
export const getMesh = (center?: string | null) => get<Mesh>(`/api/mesh${center ? `?center=${enc(center)}` : ""}`);
export const checkChannel = (channel: string) => post<ChannelCheck>("/api/channels/check", { channel });
export const setPreferences = (prefs: { auto_refresh?: boolean }) => put<{ auto_refresh: boolean }>("/api/preferences", prefs);
export const connectAccount = () => post<{ url: string }>("/api/accounts/connect");
export const disconnectAccount = (id: string) => del<{ accounts: Account[] }>(`/api/accounts/${enc(id)}`);
export const getMcp = () => get<McpSetup>("/api/mcp");

// maps
export const createMap = (channel: string, steps: number) => post<Started>("/api/maps", { channel, steps });
export const getMap = (id: string) => get<NicheMap>(mapPath(id));
export const removeMap = (id: string) => del<{ kept_as: string }>(mapPath(id));
export const restoreMap = (file: string) => post<{ id: string }>(`/api/maps/removed/${enc(file)}/restore`);
export const refreshMap = (id: string) => post<Started>(`${mapPath(id)}/refresh`);
export const deepenMap = (id: string, steps: number) => post<Started>(`${mapPath(id)}/deepen`, { steps });
export const recheckMap = (id: string) => post<Started>(`${mapPath(id)}/recheck`);
export const expandAround = (id: string, channel: string) => post<Started>(`${mapPath(id)}/expand`, { channel });
export const addCompetitors = (id: string, names: string[]) => post<Started>(`${mapPath(id)}/competitors`, { names });
export const removeChannel = (id: string, channel: string) => del<NicheMap>(`${mapPath(id)}/channels/${enc(channel)}`);
export const restoreChannel = (id: string, channel: string) => post<NicheMap>(`${mapPath(id)}/channels/${enc(channel)}/restore`);
export const setLearning = (id: string, channel: string, learn: boolean) =>
  put<NicheMap>(`${mapPath(id)}/channels/${enc(channel)}/learning`, { learn });

export interface SettingsChange {
  topics?: number;
  titles?: number;
  instructions?: string;
  check_youtube?: boolean;
  read_descriptions?: boolean;
}
export const updateSettings = (id: string, change: SettingsChange) => put<NicheMap>(`${mapPath(id)}/settings`, { ...change });

export const generateTopics = (id: string, instructions: string, files: string[]) =>
  post<Started>(`${mapPath(id)}/topics`, { instructions, files });
export const followUp = (id: string, batch: string, message: string, files: string[]) =>
  post<Started>(`${mapPath(id)}/topics/${enc(batch)}/followups`, { message, files });
export const setMark = (id: string, kind: "topics" | "titles", key: string, value: "like" | "no" | null) =>
  put<NicheMap>(`${mapPath(id)}/marks`, { kind, key, value });
export const saveTopic = (id: string, batch: string, topic: string) => post<NicheMap>(`${mapPath(id)}/saved-topics`, { batch, topic });
export const updateSaved = (id: string, saved: string, change: { status?: SavedStatus; note?: string; title?: string }) =>
  patch<NicheMap>(`${mapPath(id)}/saved-topics/${enc(saved)}`, { ...change });
export const removeSaved = (id: string, saved: string) => del<NicheMap>(`${mapPath(id)}/saved-topics/${enc(saved)}`);
export const ask = (id: string, question: string, chat: string | null, files: string[]) =>
  post<Started>(`${mapPath(id)}/chats`, { question, chat, files });
export const uploadFile = (id: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return request<Attachment>("POST", `${mapPath(id)}/files`, form);
};
export const pointsTo = (id: string) => get<{ rows: Pointer[] }>(`${mapPath(id)}/points-to`);
export const exportUrl = (id: string, what: "channels" | "breakouts") => `${mapPath(id)}/export/${what}.csv`;

// research
export type Filters = Record<string, string | number | undefined>;
export const findVideos = (filters: Filters) => post<FoundVideos>("/api/research/videos", filters);
export const findChannels = (filters: Filters) => post<FoundChannels>("/api/research/channels", filters);
export const storeStats = () => get<StoreStats>("/api/research/stats");
export const importMaps = () => post<{ imported: { channels: number; videos: number }; stats: StoreStats }>("/api/research/import");
export const computeMeanings = () => post<Started>("/api/research/meanings");

export interface LiveQuery {
  query: string;
  kind: "videos" | "channels";
  sort: string;
  uploaded: string;
  length: string;
  language: string;
  region: string;
  pages: number;
}
export const youtubeSearch = (q: LiveQuery) => post<LiveResults>("/api/youtube/search", { ...q });
export const suggestChannels = (q: string, signal?: AbortSignal) =>
  fetch(`/api/youtube/channels?q=${enc(q)}`, { signal, headers: { Accept: "application/json" } }).then(async (r) => {
    if (!r.ok) throw new ApiError(`${r.status} ${r.statusText}`, r.status);
    return ((await r.json()) as { rows: ChannelSuggestion[] }).rows;
  });

// videos
export const getTranscript = (video: string) => get<Transcript>(`/api/videos/${enc(video)}/transcript`);
export const thumbnailUrl = (video: string) => `/api/videos/${enc(video)}/thumbnail`;

export const youtubeVideo = (id: string) => `https://www.youtube.com/watch?v=${enc(id)}`;
export const youtubeChannel = (id: string) => `https://www.youtube.com/channel/${enc(id)}`;

// projects
const projectPath = (id: string) => `/api/projects/${enc(id)}`;
export interface ProjectChange {
  title?: string;
  script?: string;
  voice?: string;
  visual_instructions?: string;
  prompt_instructions?: string;
  clip_sound?: number;
}
export const listProjects = () => get<{ projects: ProjectSummary[]; voices: Record<string, string> }>("/api/projects");
export const createProject = (title: string, script: string) => post<Project>("/api/projects", { title, script });
export const projectFromTopic = (mapId: string, batch: string, topic: string) => post<Project>("/api/projects", { map_id: mapId, batch, topic });
export const getProject = (id: string) => get<Project>(projectPath(id));
export const updateProject = (id: string, change: ProjectChange) => patch<Project>(projectPath(id), { ...change });
export const deleteProject = (id: string) => del<{ deleted: string }>(projectPath(id));
export const updateScene = (id: string, index: number, change: { visual?: string; prompt?: string }) =>
  patch<Project>(`${projectPath(id)}/scenes/${index}`, { ...change });
export const draftScript = (id: string, minutes: number) => post<Started>(`${projectPath(id)}/script`, { minutes });
export const makeVoiceover = (id: string) => post<Started>(`${projectPath(id)}/voiceover`);
export const makeScenes = (id: string) => post<Started>(`${projectPath(id)}/scenes`);
export const makeClips = (id: string) => post<Started>(`${projectPath(id)}/clips`);
export const remakeClip = (id: string, index: number) => post<Started>(`${projectPath(id)}/scenes/${index}/clip`);
export const renderVideo = (id: string) => post<Started>(`${projectPath(id)}/render`);

// setup
const upload = <T>(path: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return request<T>("POST", path, form);
};
export const getSetup = () => get<SetupStatus>("/api/setup");
export const updateSetup = (values: Record<string, string>) => put<SetupStatus>("/api/setup", values);
export const uploadVertexKey = (file: File) => upload<SetupStatus>("/api/setup/vertex", file);
export const removeVertexKey = () => del<SetupStatus>("/api/setup/vertex");
export const uploadOauthClient = (file: File) => upload<SetupStatus>("/api/setup/oauth-client", file);
export const checkSetup = () => post<SetupCheck>("/api/setup/check");
