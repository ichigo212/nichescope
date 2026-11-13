import type { Link, MeshNode } from "../types";

/** Radius of the first ring, the gap between rings, the gap between lanes inside a
 * ring, and the room one channel needs along a lane. */
const FIRST = 240;
const GAP = 150;
const LANE = 44;
const ROOM = 40;
/** Outer rings sit a little lower, so the map reads as a shallow bowl. */
const SINK = 16;
const MAX_LANES = 4;
/** Average angle from a channel to its parent that is close enough (about 7 degrees). */
const NEAR_ENOUGH = 0.12;
const RELAX_ROUNDS = 400;

export interface Placed {
  x: number;
  y: number;
  z: number;
  /** Index of the channel this one hangs from, or -1 for the centre and unlinked channels. */
  parent: number;
  ring: number;
}

export interface Ring {
  step: number;
  inner: number;
  outer: number;
}

export interface Orbit {
  placed: Placed[];
  rings: Ring[];
}

const TAU = Math.PI * 2;

/**
 * Lays channels out on rings around the centre, one ring per step.
 *
 * Every channel hangs from the neighbour one step closer that it shares the strongest
 * link with, so the drawn links form a tree. Each ring is ordered by its parents'
 * order, so links between two rings never cross, and channels are spaced evenly
 * around the ring. A ring too crowded for one lane is spread over several.
 */
export function orbitLayout(nodes: MeshNode[], links: Link[], centre: string): Orbit {
  const index = new Map(nodes.map((n, i) => [n.id, i]));
  const weight = new Map<string, number>();
  const near = new Map<number, number[]>();
  for (const l of links) {
    const a = index.get(l.a);
    const b = index.get(l.b);
    if (a === undefined || b === undefined || a === b) continue;
    const key = a < b ? `${a}|${b}` : `${b}|${a}`;
    weight.set(key, Math.max(weight.get(key) ?? 0, l.coverage || 0.01));
    (near.get(a) ?? near.set(a, []).get(a)!).push(b);
    (near.get(b) ?? near.set(b, []).get(b)!).push(a);
  }
  const root = index.get(centre) ?? -1;
  const stepOf = (i: number) => (i === root ? 0 : nodes[i]!.step ?? null);

  const parent = nodes.map((_, i) => {
    const s = stepOf(i);
    if (!s) return -1;
    let best = -1;
    let bestWeight = -1;
    for (const j of near.get(i) ?? []) {
      if (stepOf(j) !== s - 1) continue;
      const w = weight.get(i < j ? `${i}|${j}` : `${j}|${i}`) ?? 0;
      if (w > bestWeight) {
        best = j;
        bestWeight = w;
      }
    }
    return best >= 0 ? best : root;
  });

  // How many channels hang below each one.
  const below = new Array<number>(nodes.length).fill(0);
  [...nodes.keys()].sort((a, b) => (stepOf(b) ?? -1) - (stepOf(a) ?? -1)).forEach((i) => {
    const p = parent[i]!;
    if (p >= 0 && p !== i) below[p] = (below[p] ?? 0) + 1 + (below[i] ?? 0);
  });

  // Rings, outermost unlinked channels last.
  const byStep = new Map<number, number[]>();
  const unlinked: number[] = [];
  nodes.forEach((_, i) => {
    if (i === root) return;
    const s = stepOf(i);
    if (s == null) unlinked.push(i);
    else (byStep.get(s) ?? byStep.set(s, []).get(s)!).push(i);
  });

  const angle = new Float64Array(nodes.length);
  const placed: Placed[] = nodes.map(() => ({ x: 0, y: 0, z: 0, parent: -1, ring: 0 }));
  const rings: Ring[] = [];
  const order = new Map<number, number>(root >= 0 ? [[root, 0]] : []);
  let inner = FIRST;
  const steps = [...byStep.keys()].sort((a, b) => a - b);

  const place = (members: number[], step: number, follow: boolean) => {
    if (!members.length) return;
    if (follow) {
      // Group by parent in the parent ring's order; within a group, strongest link first,
      // then channels with children of their own spread evenly so their groups have room.
      members.sort((a, b) => (order.get(parent[a]!) ?? 0) - (order.get(parent[b]!) ?? 0)
        || strength(b) - strength(a));
      members.splice(0, members.length, ...groups(members).flatMap(interleave));
    }
    // A crowded ring grows wider rather than deeper than MAX_LANES lanes.
    inner = Math.max(inner, (members.length * ROOM) / (MAX_LANES * TAU));
    const perLane = Math.max(6, Math.floor((TAU * inner) / ROOM));
    // A crowded ring takes more lanes, so channels can stay near their parents.
    let lanes = Math.ceil(members.length / perLane);
    let angles = spread(members, follow, lanes);
    while (lanes < MAX_LANES && displacement(members, angles) > NEAR_ENOUGH) {
      lanes++;
      angles = spread(members, follow, lanes);
    }
    members.forEach((i, k) => {
      const a = angles[k]!;
      const r = inner + (k % lanes) * LANE;
      angle[i] = a;
      order.set(i, k);
      placed[i] = { x: Math.cos(a) * r, y: -SINK * step, z: Math.sin(a) * r, parent: follow ? parent[i]! : -1, ring: step };
    });
    const outer = inner + (lanes - 1) * LANE;
    rings.push({ step, inner, outer });
    inner = outer + GAP;
  };

  /** Angles for one ring, in order: each channel as near its parent's angle as the
   * spacing allows. A full ring is spaced evenly. */
  function spread(members: number[], follow: boolean, lanes: number): number[] {
    const n = members.length;
    const gap = ROOM / (inner * lanes);
    const even = members.map((_, k) => (TAU * k) / n);
    if (!follow || n * gap >= TAU * 0.9 || members.every((i) => parent[i] === root)) return even;
    // Where each would like to sit: its group fanned out around the parent's angle.
    const wish: number[] = [];
    for (let k = 0; k < n; ) {
      const p = parent[members[k]!]!;
      let end = k;
      while (end < n && parent[members[end]!] === p) end++;
      const size = end - k;
      for (let j = 0; j < size; j++) wish.push(angle[p]! + (j - (size - 1) / 2) * gap);
      k = end;
    }
    for (let k = 1; k < n; k++) {
      while (wish[k]! < wish[k - 1]! - Math.PI) wish[k] = wish[k]! + TAU;
    }
    // Push neighbours closer than the gap apart, both ways, until none are.
    const at = wish.slice();
    for (let round = 0; round < RELAX_ROUNDS; round++) {
      let moved = false;
      for (let k = 0; k < n; k++) {
        const j = (k + 1) % n;
        const d = (j ? at[j]! : at[0]! + TAU) - at[k]!;
        if (d < gap - 1e-6) {
          const push = (gap - d) / 2;
          at[k] = at[k]! - push;
          at[j] = at[j]! + push;
          moved = true;
        }
      }
      if (!moved) break;
    }
    return at;
  }

  function displacement(members: number[], angles: number[]): number {
    let sum = 0;
    let count = 0;
    members.forEach((i, k) => {
      const p = parent[i]!;
      if (p < 0 || p === root) return;
      const d = Math.abs(Math.atan2(Math.sin(angles[k]! - angle[p]!), Math.cos(angles[k]! - angle[p]!)));
      sum += d;
      count++;
    });
    return count ? sum / count : 0;
  }

  function groups(members: number[]): number[][] {
    const out: number[][] = [];
    for (const i of members) {
      const last = out.at(-1);
      if (last && parent[last[0]!] === parent[i]) last.push(i);
      else out.push([i]);
    }
    return out;
  }

  /** Channels with children at even intervals through the group, leaves around them. */
  function interleave(group: number[]): number[] {
    const heavy = group.filter((i) => (below[i] ?? 0) > 0).sort((a, b) => below[b]! - below[a]!);
    if (!heavy.length || heavy.length === group.length) return group;
    const light = group.filter((i) => !(below[i] ?? 0));
    const out: number[] = [];
    const every = group.length / heavy.length;
    let h = 0;
    for (let k = 0; k < group.length; k++) {
      if (h < heavy.length && k >= Math.round(h * every + every / 2 - 0.5)) out.push(heavy[h++]!);
      else out.push(light.shift() ?? heavy[h++]!);
    }
    return out;
  }

  function strength(i: number) {
    const p = parent[i]!;
    return p < 0 ? 0 : weight.get(i < p ? `${i}|${p}` : `${p}|${i}`) ?? 0;
  }

  for (const s of steps) place(byStep.get(s)!, s, true);
  place(unlinked, (steps.at(-1) ?? 0) + 1, false);
  return { placed, rings };
}

/** Points along the curved link from a parent to a child: it leaves the parent heading
 * outward and arrives at the child from the inside, like branches of a radial tree. */
export function curve(from: { x: number; y: number; z: number }, to: { x: number; y: number; z: number }, segments: number, out: Float32Array, offset: number) {
  const rFrom = Math.hypot(from.x, from.z);
  const rTo = Math.hypot(to.x, to.z);
  const mid = (rFrom + rTo) / 2;
  const aTo = Math.atan2(to.z, to.x);
  const aFrom = rFrom < 1 ? aTo : Math.atan2(from.z, from.x);
  const c1 = { x: Math.cos(aFrom) * (rFrom < 1 ? mid * 0.4 : mid), z: Math.sin(aFrom) * (rFrom < 1 ? mid * 0.4 : mid) };
  const c2 = { x: Math.cos(aTo) * mid, z: Math.sin(aTo) * mid };
  for (let s = 0; s <= segments; s++) {
    const t = s / segments;
    const u = 1 - t;
    const k = offset + s * 3;
    out[k] = u * u * u * from.x + 3 * u * u * t * c1.x + 3 * u * t * t * c2.x + t * t * t * to.x;
    out[k + 1] = from.y + (to.y - from.y) * t;
    out[k + 2] = u * u * u * from.z + 3 * u * u * t * c1.z + 3 * u * t * t * c2.z + t * t * t * to.z;
  }
}
