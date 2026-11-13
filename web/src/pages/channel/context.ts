import { createContext, useContext } from "react";

import { attempt } from "../../toasts";
import type { NicheMap } from "../../types";

export interface MapCtx {
  m: NicheMap;
  /** Replace the map with one a request answered with. */
  setM: (m: NicheMap) => void;
  reload: () => Promise<NicheMap | null>;
  busy: boolean;
}

export const MapContext = createContext<MapCtx | null>(null);

export function useMap(): MapCtx {
  const ctx = useContext(MapContext);
  if (!ctx) throw new Error("useMap outside a channel page");
  return ctx;
}

/** Run a request that answers with the updated map, and show it. */
export function useMapChange() {
  const { setM } = useMap();
  return async (request: Promise<NicheMap>) => {
    const m = await attempt(request);
    if (m) setM(m);
    return m;
  };
}

export const newestFirst = <T extends { at: string }>(rows: T[]) => [...rows].sort((a, b) => b.at.localeCompare(a.at));
