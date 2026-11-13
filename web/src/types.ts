export type Grade = "close" | "medium" | "far";

export interface Video {
  id: string;
  title: string;
  views: number | null;
  published_at: string;
  thumbnail: string;
  seconds: number | null;
  outlier: number | null;
  on_topic: boolean | null;
  channel?: string;
  channelId?: string;
}

export interface HomeBreakout extends Video {
  channel: string;
  channelId: string;
  mapId: string;
  mapTitle: string;
}

export interface MapChannel {
  id: string;
  title: string;
  handle: string;
  avatar: string;
  subscribers: number | null;
  views30d: number | null;
  usual: number | null;
  grade: Grade;
  appearances: number;
  coverage: number;
  viaCoverage: number | null;
  viaTitle: string | null;
  breakout: number | null;
  via: string | null;
  step: number;
  promoted: number | null;
  proven: number | null;
  provenVideos: { id: string; title: string; views: number }[];
  added: boolean;
  off: boolean;
  topic: number | null;
  /** The model's verdict: the same kind of videos, close to it, something else, or not sure. */
  fit: "same" | "adjacent" | "unrelated" | "unclear" | null;
  rising: number | null;
  startedAt: string;
  isNew: boolean;
  language: string;
  minutes: number | null;
  breakouts: Video[];
}

/** On the map in its own right: recommended often, judged the same kind of channel, sending
 * real viewers, or added by hand. Other far channels only show when asked for. */
export function isNear(c: MapChannel) {
  return c.grade !== "far" || c.fit === "same" || !!c.proven || c.added;
}

export interface Link {
  a: string;
  b: string;
  coverage: number;
}

export interface Attachment {
  id: string;
  name: string;
  kind: "image" | "file";
  url?: string;
}

export interface OwnVideo {
  id: string;
  title: string;
  thumbnail: string;
  published_at: string;
  views: number | null;
  period_views: number | null;
  avg_view_pct: number | null;
  subs: number | null;
  impressions?: number | null;
  ctr?: number | null;
  verdict: string;
  note: string;
}

export interface Reasons {
  proven?: string;
  gap?: string;
  angle?: string;
  risk?: string;
}

export interface OnYoutube {
  video: string;
  title: string;
  channel: string;
  views: number | null;
  days: number | null;
  mine: boolean;
}

export interface Topic {
  topic: string;
  why: string;
  detail: string;
  reasons: Reasons;
  expectedViews: { low: number; high: number } | null;
  titles: string[];
  fit: number | null;
  onYoutube: OnYoutube | null;
  /** The named series, work, person or place the idea is about, and where that name is written. */
  name: { name: string; source: string | null; video: string | null } | null;
  closestOwn: OwnVideo | null;
  evidenceLost: number;
  evidence: (Video & { channel: string; searched?: boolean })[];
}

export interface FollowUp {
  role: "user" | "model";
  content: string;
  at: string;
  files: Attachment[];
  addedTopics: number;
  titlesFor: number[];
}

export interface Batch {
  id: string;
  at: string;
  instructions: string;
  /** The subject the request named, and what searching for it found. */
  searched: { subject: string; queries: string[]; onMap: number; onYoutube: number } | null;
  files: Attachment[];
  learnedFrom: number | null;
  analysis: string;
  followups: FollowUp[];
  topics: Topic[];
}

export interface Mention {
  id: string;
  title: string;
  avatar: string;
  subscribers: number | null;
  views30d: number | null;
  breakout: number | null;
}

export interface ChatMessage {
  role: "user" | "model";
  content: string;
  at: string;
  files: Attachment[];
  mentions: Mention[];
}

export interface Chat {
  id: string;
  at: string;
  messages: ChatMessage[];
}

export type SavedStatus = "planned" | "working" | "done";

export interface SavedTopic {
  id: string;
  topic: string;
  why: string;
  detail?: string;
  titles: string[];
  status: SavedStatus;
  note: string;
  title: string;
  at: string;
  evidence: Video[];
}

export interface TrafficSource {
  source: string;
  views: number;
  minutes: number;
  share: number;
}

export interface Own {
  windowDays: number | null;
  sources: TrafficSource[];
  medians: { retention?: number | null; ctr?: number | null };
  /** When impressions and click-through rate were last imported from Studio. */
  reachAt: string | null;
  videos: OwnVideo[];
  traffic: {
    id: string;
    title: string;
    views: number;
    minutes: number;
    top: { id: string; title: string; views: number } | null;
  }[];
  accuracy: {
    real: number;
    found: number;
    near: number;
    mapped: number;
    views_named: number;
    views_found: number;
    views_suggested: number | null;
  } | null;
}

export interface MapSettings {
  topics: number;
  titles: number;
  instructions: string;
  check_youtube: boolean;
  read_descriptions: boolean;
}

export interface NicheMap {
  id: string;
  title: string;
  avatar: string;
  handle: string;
  subscribers: number | null;
  usual: number | null;
  views30d: number | null;
  videosRead: number;
  scannedAt: string;
  channels: MapChannel[];
  links: Link[];
  expanded: string[];
  breakouts: (Video & { channel: string; channelId: string })[];
  breakingOut: number;
  batches: Batch[];
  chats: Chat[];
  marks: { topics: Record<string, string>; titles: Record<string, string> };
  confidence: { why: string; instead: { id: string; title: string } | null } | null;
  own: Own | null;
  ownError: string | null;
  isOwn: boolean;
  savedTopics: SavedTopic[];
  settings: MapSettings;
  limits: { topics: number; titles: number; instructions: number };
  setAside: { id: string; title: string; avatar: string; topic: number | null; margin: number | null; fit: string | null; seen: string }[];
  uploads: { recent: Video[]; popular: Video[] };
  removed: { id: string; title: string; at: string }[];
}

export interface Card {
  id: string;
  title: string;
  avatar: string;
  handle: string;
  subscribers: number | null;
  scannedAt: string;
  near: number;
  shown: number;
  isOwn: boolean;
  dots: { avatar: string; ring: 0 | 1 }[];
}

export interface RemovedMap {
  file: string;
  channel_id: string;
  title: string;
  avatar: string;
  at: string;
}

export interface Home {
  cards: Card[];
  breakouts: HomeBreakout[];
  removedMaps: RemovedMap[];
}

export interface MeshNode {
  id: string;
  title: string;
  avatar: string;
  handle: string;
  subscribers: number | null;
  views30d: number | null;
  usual: number | null;
  breakout: number | null;
  startedAt: string;
  minutes: number | null;
  language: string;
  maps: string[];
  mapped: boolean;
  off: boolean;
  fit: "same" | "adjacent" | "unclear" | null;
  step?: number | null;
}

export interface Mesh {
  center: string | null;
  nodes: MeshNode[];
  links: Link[];
  maps: { id: string; title: string }[];
}

export type JobStatus = "running" | "done" | "failed";

export interface Job {
  id: string;
  kind: string;
  label: string;
  map_id: string | null;
  status: JobStatus;
  message: string;
  error: string | null;
  started_at?: number;
  finished_at?: number;
}

export interface JobEvent {
  type: "job";
  job: Job;
  map_id?: string;
  project_id?: string;
  problems?: string[];
  result?: unknown;
}

export interface Account {
  id: string;
  title: string;
  handle: string;
}

export interface Status {
  job: Job | null;
  recentJobs: Job[];
  quotaLeft: number;
  quotaPerDay: number;
  accounts: Account[];
  configured: { model: boolean; youtube: boolean; oauth: boolean };
  preferences: { auto_refresh: boolean };
}

export interface McpSetup {
  stdio: { command: string; args: string[] };
  http: string;
  claudeCode: string;
  claudeCodeHttp: string;
  desktopConfig: string;
}

export interface ChannelSuggestion {
  id: string;
  title: string;
  avatar: string;
  detail: string;
}

export interface ChannelCheck {
  id: string;
  title: string;
  handle: string;
  avatar: string;
  subscribers: number;
  videos: number;
  small: boolean;
  mapped: boolean;
}

export interface StoreStats {
  channels: number;
  channels_with_videos: number;
  channels_read_in_full: number;
  videos: number;
  videos_with_meaning: number;
  oldest_video: string;
  last_read: string;
  days_of_reads: number;
}

export interface FoundVideo {
  id: string;
  channel_id: string;
  title: string;
  published_at: string;
  seconds: number | null;
  views: number | null;
  thumbnail: string;
  channel: string;
  channel_subscribers: number | null;
  usual: number | null;
  outlier: number | null;
  per_day: number | null;
  gaining: number | null;
  similarity?: number | null;
}

export interface MapPlace {
  map: string;
  map_id: string;
  grade: string;
  coverage: number;
  proven: number;
  off: boolean;
}

export interface FoundChannel {
  id: string;
  title: string;
  handle: string;
  avatar: string;
  subscribers: number | null;
  started_at: string;
  video_count: number | null;
  usual: number | null;
  views_30d: number | null;
  minutes: number | null;
  breakout: number | null;
  matches: number;
  breakout_video: { id: string; title: string; views: number } | null;
  maps: MapPlace[];
}

export interface FoundVideos {
  total: number;
  more: boolean;
  videos: FoundVideo[];
  stats: StoreStats;
}

export interface FoundChannels {
  total: number;
  more: boolean;
  channels: FoundChannel[];
  stats: StoreStats;
}

export interface LiveMapPlace {
  map: string;
  mapId: string;
  grade: string | null;
}

export interface LiveVideo {
  id: string;
  title: string;
  channel: string;
  channel_id: string;
  channel_subscribers: number | null;
  views: number | null;
  age_text: string;
  age_days: number | null;
  live: boolean;
  seconds: number | null;
  thumbnail: string;
  usual: number | null;
  outlier: number | null;
  per_day: number | null;
  maps: LiveMapPlace[];
}

export interface LiveChannel {
  id: string;
  title: string;
  avatar: string;
  detail: string;
  subscribers: number | null;
  usual: number | null;
  views_30d: number | null;
  maps: LiveMapPlace[];
}

export interface LiveResults {
  query: string;
  kind: "videos" | "channels";
  pages: number;
  results: (LiveVideo | LiveChannel)[];
  judged: number;
  note?: string;
}

export interface Pointer {
  id: string;
  title: string;
  real_views: number | null;
  coverage: number;
  maps: number;
}

export interface Transcript {
  video: string;
  title: string;
  language: string;
  words: number;
  text: string;
  segments: { start: number; text: string }[];
}

export type ProjectStep = "script" | "scenes" | "clips" | "done";

export interface ProjectSource {
  map_id?: string;
  batch?: string;
  topic?: string;
  title?: string;
}

export interface ProjectSummary {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string | null;
  step: ProjectStep;
  scenes: number;
  clips: number;
  source: ProjectSource;
}

export interface Clip {
  url: string | null;
  speech: boolean;
  error: string | null;
  at: string | null;
}

export interface Scene {
  index: number;
  text: string;
  start: number;
  end: number;
  clipSeconds: number;
  visual: string;
  prompt: string;
  clip: Clip | null;
}

export interface Project {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string | null;
  source: ProjectSource;
  script: string;
  voice: string;
  visualInstructions: string;
  promptInstructions: string;
  clipSound: number;
  voiceover: { url: string; seconds: number; at: string } | null;
  scenes: Scene[];
  render: { status: "rendering" | "done" | "failed"; url: string | null; at: string; error: string | null } | null;
  estimate: { voice_seconds: number; scenes: number; clip_seconds: number; video_cost: number };
}

export type SetupModelKey =
  | "GEMINI_MODEL"
  | "GEMINI_LIGHT_MODEL"
  | "GEMINI_EMBED_MODEL"
  | "GEMINI_TTS_MODEL"
  | "VIDEO_MODEL"
  | "VIDEO_LOCATION"
  | "VIDEO_PRICE_PER_SECOND"
  | "VERTEX_LOCATION";

export interface SetupStatus {
  geminiApiKey: string | null;
  vertex: { project: string | null } | null;
  youtubeApiKey: string | null;
  youtubeSource: "public" | "api";
  oauthClient: boolean;
  models: Record<SetupModelKey, string>;
  ready: { model: boolean; video: boolean; youtube: boolean; analytics: boolean };
}

export interface CheckResult {
  ok: boolean;
  error?: string;
}

export interface SetupCheck {
  model: CheckResult;
  youtube: CheckResult;
  video?: CheckResult;
}

export interface StudyStyle {
  n: number;
  face: number;
  strong_emotion: number;
  shows_a_situation: number;
  arrow_or_circle: number;
  split_panels: number;
  bright: number;
  dark: number;
  faces: number;
  words: number;
  [key: string]: number;
}

/** What the near competitors of a map do differently when their videos break out. */
export interface Study {
  at: string;
  stale: boolean;
  channels: number;
  videos: number;
  usual: number;
  uploads30: number;
  recentTitles: number;
  findings: { key: string; title: string; finding: string; action: string; basis: string }[];
  titles: { key: string; label: string; count: number; share: number; ours: number | null; with: number | null; without: number | null; up: number; down: number }[];
  rising: { key: string; label: string; was: number; now: number }[];
  styles: { winners: StudyStyle | null; losers: StudyStyle | null; ours: StudyStyle | null };
  styleRows: { key: string; label: string }[];
  escapes: { channel: string; subs: number; videos: number; hit: number | null; days: number | null; title: string; views: number | null }[];
  theirBest: Video[];
  yourLatest: Video[];
}
