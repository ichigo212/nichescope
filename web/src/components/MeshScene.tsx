import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { times } from "../format";
import type { Link, MeshNode } from "../types";
import { curve, orbitLayout } from "./orbitLayout";

const ATLAS = 4096;
const CELL = 96;
const PER_ROW = Math.floor(ATLAS / CELL);
/** Avatars loading at once. Browsers allow six connections per host and the event
 * stream holds one, so this leaves room for the page's own requests. */
const LOADERS = 4;
const LABELS = 8;
const BADGES = 12;
const SEGMENTS = 12;
/** Links fade out over this angle around the ring, down to FAR_LINK of their strength. */
const LINK_FADE = Math.PI / 3;
const FAR_LINK = 0.08;
/** Seconds for the opening: rings unfold one after another. */
const UNFOLD = 0.55;
const UNFOLD_STAGGER = 0.4;

export const FIT_COLOURS = {
  centre: "#ffffff",
  same: "#5ec8f2",
  adjacent: "#a48bff",
  other: "#5d6679",
} as const;
const COLOUR = {
  centre: new THREE.Color(FIT_COLOURS.centre),
  same: new THREE.Color(FIT_COLOURS.same),
  adjacent: new THREE.Color(FIT_COLOURS.adjacent),
  other: new THREE.Color(FIT_COLOURS.other),
};

export interface MeshSceneProps {
  nodes: MeshNode[];
  links: Link[];
  centre: string;
  depth: number;
  dimmed: Set<string>;
  hidden: Set<string>;
  badges: boolean;
  badgeMin: number;
  selected: string | null;
  onSelect: (id: string | null) => void;
}

const vertex = /* glsl */ `
  attribute float aSize;
  attribute float aCell;
  attribute vec3 aRing;
  attribute float aAlpha;
  attribute float aLift;
  varying float vCell;
  varying vec3 vRing;
  varying float vAlpha;
  varying float vLift;
  uniform float uScale;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = aSize * (1.0 + 0.4 * aLift) * uScale / -mv.z;
    vCell = aCell;
    vRing = aRing;
    vAlpha = aAlpha;
    vLift = aLift;
  }
`;

const fragment = /* glsl */ `
  uniform sampler2D uAtlas;
  uniform float uPerRow;
  uniform float uCell;
  varying float vCell;
  varying vec3 vRing;
  varying float vAlpha;
  varying float vLift;
  void main() {
    vec2 p = gl_PointCoord * 2.0 - 1.0;
    float r = length(p);
    if (r > 1.0 || vAlpha < 0.01) discard;
    float face = 0.80;
    float edge = fwidth(r);
    vec4 colour;
    if (r < face) {
      vec3 fill = vRing * 0.3 + 0.06;
      if (vCell >= 0.0) {
        vec2 cell = vec2(mod(vCell, uPerRow), floor(vCell / uPerRow));
        vec2 local = (gl_PointCoord - 0.5) / face * 0.96 + 0.5;
        fill = texture2D(uAtlas, (cell + local) * uCell).rgb;
      }
      colour = vec4(fill, 1.0);
      colour.rgb = mix(colour.rgb, vRing, smoothstep(face - edge * 2.0, face, r));
    } else {
      float ring = 1.0 - smoothstep(0.88, 0.88 + edge * 2.0, r);
      float glow = (1.0 - smoothstep(0.88, 1.0, r)) * (0.3 + 0.7 * vLift);
      colour = vec4(vRing, max(ring, glow * 0.6));
    }
    gl_FragColor = vec4(colour.rgb, colour.a * vAlpha);
  }
`;

function colourFor(n: MeshNode, centre: string) {
  if (n.id === centre) return COLOUR.centre;
  if (n.fit === "same") return COLOUR.same;
  if (n.fit === "adjacent") return COLOUR.adjacent;
  return COLOUR.other;
}

function sizeFor(n: MeshNode, centre: string) {
  if (n.id === centre) return 78;
  const views = n.views30d ?? 0;
  return 15 + Math.min(28, Math.sqrt(views) / 42) + (n.mapped ? 6 : 0);
}

function reducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

const ease = (t: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);

/** The mesh as rings around the centre channel: drag to turn, wheel to zoom, click a
 * channel to fly to it. Only the link each channel hangs from is drawn; hovering or
 * selecting a channel shows all of its links. */
export function MeshScene(props: MeshSceneProps) {
  const host = useRef<HTMLDivElement>(null);
  const overlay = useRef<HTMLDivElement>(null);
  const live = useRef(props);
  live.current = props;
  const api = useRef<{ refresh: () => void; focus: (id: string | null) => void } | null>(null);

  useEffect(() => {
    const el = host.current;
    const labels = overlay.current;
    if (!el || !labels) return;
    const still = reducedMotion();
    const { nodes, links, centre } = live.current;
    const { placed, rings } = orbitLayout(nodes, links, centre);
    const count = nodes.length;
    const index = new Map(nodes.map((n, i) => [n.id, i]));

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, el.clientWidth / el.clientHeight, 1, 20000);
    camera.position.set(0, 1300, 1500);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.autoRotate = !still;
    controls.autoRotateSpeed = 0.22;
    controls.minDistance = 120;
    controls.maxDistance = 9000;
    controls.maxPolarAngle = Math.PI * 0.47;

    // A sparse field of dust far behind the rings, for depth.
    const dust = new THREE.BufferGeometry();
    const dustAt = new Float32Array(1200 * 3);
    for (let i = 0; i < 1200; i++) {
      const r = 3000 + Math.random() * 5000;
      const a = Math.random() * Math.PI * 2;
      const b = Math.acos(2 * Math.random() - 1);
      dustAt.set([r * Math.sin(b) * Math.cos(a), r * Math.cos(b), r * Math.sin(b) * Math.sin(a)], i * 3);
    }
    dust.setAttribute("position", new THREE.BufferAttribute(dustAt, 3));
    scene.add(new THREE.Points(dust, new THREE.PointsMaterial({ color: 0x40507a, size: 1.6, sizeAttenuation: false, transparent: true, opacity: 0.55 })));

    // Faint guide circles, one per ring.
    const guides: THREE.LineLoop[] = rings.map((r) => {
      const g = new THREE.BufferGeometry();
      const at = new Float32Array(256 * 3);
      const radius = (r.inner + r.outer) / 2;
      for (let k = 0; k < 256; k++) {
        const a = (k / 256) * Math.PI * 2;
        at.set([Math.cos(a) * radius, -16 * r.step - 2, Math.sin(a) * radius], k * 3);
      }
      g.setAttribute("position", new THREE.BufferAttribute(at, 3));
      const loop = new THREE.LineLoop(g, new THREE.LineBasicMaterial({ color: 0x1c2a44, transparent: true, opacity: 0 }));
      loop.userData.step = r.step;
      scene.add(loop);
      return loop;
    });

    // Channels.
    const geometry = new THREE.BufferGeometry();
    const position = new Float32Array(count * 3);
    const size = new Float32Array(count);
    const cell = new Float32Array(count).fill(-1);
    const ring = new Float32Array(count * 3);
    const alpha = new Float32Array(count);
    const lift = new Float32Array(count);
    const alphaTarget = new Float32Array(count);
    const liftTarget = new Float32Array(count);
    nodes.forEach((n, i) => {
      size[i] = sizeFor(n, centre);
      colourFor(n, centre).toArray(ring, i * 3);
    });
    geometry.setAttribute("position", new THREE.BufferAttribute(position, 3));
    geometry.setAttribute("aSize", new THREE.BufferAttribute(size, 1));
    geometry.setAttribute("aCell", new THREE.BufferAttribute(cell, 1));
    geometry.setAttribute("aRing", new THREE.BufferAttribute(ring, 3));
    geometry.setAttribute("aAlpha", new THREE.BufferAttribute(alpha, 1));
    geometry.setAttribute("aLift", new THREE.BufferAttribute(lift, 1));
    // Points are drawn back to front, so nearer channels cover farther ones.
    const drawOrder = new Uint32Array(count).map((_, i) => i);
    const depthOf = new Float32Array(count);
    geometry.setIndex(new THREE.BufferAttribute(drawOrder, 1));
    const sortByDepth = () => {
      const e = camera.matrixWorldInverse.elements;
      for (let i = 0; i < count; i++) {
        depthOf[i] = e[2]! * position[i * 3]! + e[6]! * position[i * 3 + 1]! + e[10]! * position[i * 3 + 2]! + e[14]!;
      }
      drawOrder.set(Array.from(drawOrder).sort((a, b) => depthOf[a]! - depthOf[b]!));
      geometry.index!.needsUpdate = true;
    };

    const atlasCanvas = document.createElement("canvas");
    atlasCanvas.width = atlasCanvas.height = ATLAS;
    const atlas = atlasCanvas.getContext("2d")!;
    const texture = new THREE.CanvasTexture(atlasCanvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.flipY = false;
    texture.minFilter = THREE.LinearMipmapLinearFilter;
    texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
    const material = new THREE.ShaderMaterial({
      vertexShader: vertex,
      fragmentShader: fragment,
      transparent: true,
      depthWrite: false,
      uniforms: { uAtlas: { value: texture }, uPerRow: { value: PER_ROW }, uCell: { value: CELL / ATLAS }, uScale: { value: el.clientHeight * 0.9 * renderer.getPixelRatio() } },
    });
    const points = new THREE.Points(geometry, material);
    points.frustumCulled = false;
    points.renderOrder = 2;
    scene.add(points);

    // The tree: one curved link from each channel to the channel it hangs from.
    const tree = placed.map((p, i) => [p.parent, i] as const).filter(([p]) => p >= 0);
    // At rest, a link that travels far around the ring is drawn fainter, so a channel with
    // hundreds of children does not paint a fan over the middle. Pointing at it shows them all.
    const reach = tree.map(([a, b]) => {
      const pa = placed[a]!;
      const pb = placed[b]!;
      if (Math.hypot(pa.x, pa.z) < 1) return 1;
      let d = Math.abs(Math.atan2(pa.z, pa.x) - Math.atan2(pb.z, pb.x));
      if (d > Math.PI) d = Math.PI * 2 - d;
      return Math.max(FAR_LINK, 1 - d / LINK_FADE);
    });
    const per = SEGMENTS + 1;
    const treeGeometry = new THREE.BufferGeometry();
    const treeAt = new Float32Array(tree.length * per * 3);
    const treeColour = new Float32Array(tree.length * per * 3);
    const treeIndex: number[] = [];
    tree.forEach((_, k) => {
      for (let s = 0; s < SEGMENTS; s++) treeIndex.push(k * per + s, k * per + s + 1);
    });
    treeGeometry.setAttribute("position", new THREE.BufferAttribute(treeAt, 3));
    treeGeometry.setAttribute("color", new THREE.BufferAttribute(treeColour, 3));
    treeGeometry.setIndex(treeIndex);
    // Links only add light: they never write alpha, so a faint or hidden link cannot
    // darken the page behind the transparent canvas.
    const lineMaterial = () => new THREE.LineBasicMaterial({
      vertexColors: true, transparent: true, depthWrite: false, blending: THREE.CustomBlending,
      blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor,
      blendSrcAlpha: THREE.ZeroFactor, blendDstAlpha: THREE.OneFactor,
    });
    const treeLines = new THREE.LineSegments(treeGeometry, lineMaterial());
    treeLines.frustumCulled = false;
    scene.add(treeLines);

    // Every other link of the channel in focus, drawn only while it is in focus.
    const neighbours = new Map<number, Set<number>>();
    for (const l of links) {
      const a = index.get(l.a);
      const b = index.get(l.b);
      if (a === undefined || b === undefined || a === b) continue;
      (neighbours.get(a) ?? neighbours.set(a, new Set()).get(a)!).add(b);
      (neighbours.get(b) ?? neighbours.set(b, new Set()).get(b)!).add(a);
    }
    const focusGeometry = new THREE.BufferGeometry();
    const focusLines = new THREE.LineSegments(focusGeometry, lineMaterial());
    focusLines.frustumCulled = false;
    scene.add(focusLines);

    let hovered = -1;
    let selected = -1;
    const at = new THREE.Vector3();
    const point = (i: number) => ({ x: position[i * 3]!, y: position[i * 3 + 1]!, z: position[i * 3 + 2]! });

    function radius(i: number) {
      at.set(position[i * 3]!, position[i * 3 + 1]!, position[i * 3 + 2]!).applyMatrix4(camera.matrixWorldInverse);
      return (size[i]! * (1 + 0.4 * lift[i]!) * el!.clientHeight * 0.9) / Math.max(1, -at.z) / 2;
    }

    function drawFocus(focus: number) {
      const others = focus >= 0 ? [...(neighbours.get(focus) ?? [])].filter((j) => alphaTarget[j]! > 0) : [];
      const pts = new Float32Array(others.length * per * 3);
      const cols = new Float32Array(others.length * per * 3);
      const idx: number[] = [];
      others.forEach((j, k) => {
        const [from, to] = placed[j]!.ring < placed[focus]!.ring ? [j, focus] : [focus, j];
        curve(point(from), point(to), SEGMENTS, pts, k * per * 3);
        const c = new THREE.Color().copy(colourFor(nodes[j]!, centre)).multiplyScalar(0.9);
        for (let s = 0; s < per; s++) c.toArray(cols, (k * per + s) * 3);
        for (let s = 0; s < SEGMENTS; s++) idx.push(k * per + s, k * per + s + 1);
      });
      focusGeometry.setAttribute("position", new THREE.BufferAttribute(pts, 3));
      focusGeometry.setAttribute("color", new THREE.BufferAttribute(cols, 3));
      focusGeometry.setIndex(idx);
    }

    function refresh() {
      const p = live.current;
      const focus = hovered >= 0 ? hovered : selected;
      const near = focus >= 0 ? neighbours.get(focus) ?? new Set<number>() : null;
      nodes.forEach((n, i) => {
        const inDepth = n.id === p.centre || (n.step != null && n.step <= p.depth);
        let a = !inDepth || p.hidden.has(n.id) ? 0 : p.dimmed.has(n.id) ? 0.14 : 1;
        if (near && a > 0 && i !== focus && !near.has(i)) a = Math.min(a, 0.16);
        alphaTarget[i] = a;
        liftTarget[i] = i === focus ? 1 : near?.has(i) ? 0.45 : 0;
      });
      tree.forEach(([a, b], k) => {
        const shown = Math.min(alphaTarget[a]!, alphaTarget[b]!);
        const lit = focus >= 0 && (a === focus || b === focus);
        const strength = (lit ? 0 : near ? 0.035 : placed[b]!.ring > 1 ? 0.13 : 0.16) * shown * reach[k]!;
        const c = colourFor(nodes[b]!, centre);
        for (let s = 0; s < per; s++) {
          // Brighter near the child, fading towards the parent.
          const fade = strength * (0.35 + 0.65 * (s / SEGMENTS));
          treeColour.set([c.r * fade, c.g * fade, c.b * fade], (k * per + s) * 3);
        }
      });
      treeGeometry.attributes.color!.needsUpdate = true;
      drawFocus(focus);
      for (const g of guides) {
        (g.material as THREE.LineBasicMaterial).opacity = g.userData.step <= p.depth ? 0.55 : 0;
      }
    }
    refresh();

    // Avatars are drawn into one texture atlas as they arrive, nearest rings first.
    let atlasDirty = false;
    // Drawn avatars wait here until the atlas reaches the GPU, so none shows as an empty disc.
    const drawn: number[] = [];
    let next = 0;
    let stopped = false;
    const loading = new Set<HTMLImageElement>();
    const loadOrder = [...nodes.keys()].sort((a, b) => placed[a]!.ring - placed[b]!.ring || size[b]! - size[a]!);
    function loadNext() {
      if (stopped) return;
      const i = loadOrder[next++];
      if (i === undefined || i >= PER_ROW * PER_ROW) return;
      const src = nodes[i]!.avatar;
      if (!src) return loadNext();
      const img = new Image();
      loading.add(img);
      img.onload = () => {
        loading.delete(img);
        if (stopped) return;
        atlas.drawImage(img, (i % PER_ROW) * CELL, Math.floor(i / PER_ROW) * CELL, CELL, CELL);
        drawn.push(i);
        atlasDirty = true;
        loadNext();
      };
      img.onerror = () => {
        loading.delete(img);
        loadNext();
      };
      img.src = src.startsWith("data:") ? src : `/api/image?src=${encodeURIComponent(src)}`;
    }
    for (let k = 0; k < LOADERS; k++) loadNext();

    // Labels and breakout badges are HTML, positioned over the scene each frame.
    const tags = new Map<number, HTMLDivElement>();
    function tag(i: number, kind: "label" | "badge"): HTMLDivElement {
      const key = kind === "label" ? i : -i - 1;
      let div = tags.get(key);
      if (!div) {
        div = document.createElement("div");
        const n = nodes[i]!;
        div.className = kind === "label" ? (n.id === centre ? "mesh-label mesh-label-centre" : "mesh-label") : "mesh-badge";
        div.textContent = kind === "label" ? n.title : times(n.breakout ?? 0);
        labels!.appendChild(div);
        tags.set(key, div);
      }
      return div;
    }
    const projected = new THREE.Vector3();
    function rank(i: number) {
      const p = live.current;
      if (i === selected || i === hovered) return Infinity;
      if (nodes[i]!.id === p.centre) return Number.MAX_VALUE;
      return nodes[i]!.views30d ?? 0;
    }
    function placeTags() {
      const p = live.current;
      const w = el!.clientWidth;
      const h = el!.clientHeight;
      const visible = nodes.map((_, i) => i).filter((i) => alphaTarget[i]! > 0.5);
      const ranked = [...visible].filter((i) => nodes[i]!.id !== p.centre)
        .sort((a, b) => (nodes[b]!.views30d ?? 0) - (nodes[a]!.views30d ?? 0));
      const named = new Set(visible.filter((i) => nodes[i]!.id === p.centre).concat(ranked.slice(0, LABELS)));
      if (hovered >= 0) named.add(hovered);
      if (selected >= 0) named.add(selected);
      const badged = new Set(p.badges ? [...visible].filter((i) => (nodes[i]!.breakout ?? 0) >= p.badgeMin)
        .sort((a, b) => (nodes[b]!.breakout ?? 0) - (nodes[a]!.breakout ?? 0)).slice(0, BADGES) : []);
      // Labels go down most important first; one that would overlap a label already placed
      // is hidden, so names never print over each other.
      const priority = [...named].sort((a, b) => rank(b) - rank(a));
      const taken: [number, number, number, number][] = [];
      for (const i of priority) {
        const div = tag(i, "label");
        projected.set(position[i * 3]!, position[i * 3 + 1]!, position[i * 3 + 2]!).project(camera);
        const x = (projected.x * 0.5 + 0.5) * w;
        const y = (-projected.y * 0.5 + 0.5) * h + radius(i) + 4;
        const half = div.offsetWidth / 2 + 4;
        const box: [number, number, number, number] = [x - half, y, x + half, y + div.offsetHeight];
        const clear = projected.z <= 1 && !taken.some((t) => box[0] < t[2] && box[2] > t[0] && box[1] < t[3] && box[3] > t[1]);
        div.style.opacity = clear ? String(alpha[i]!) : "0";
        div.style.transform = `translate(${x}px, ${y}px) translate(-50%, 0)`;
        if (clear) taken.push(box);
      }
      for (const [key, div] of tags) {
        const i = key >= 0 ? key : -key - 1;
        if (key >= 0) {
          if (!named.has(i)) div.style.opacity = "0";
          continue;
        }
        if (!badged.has(i)) {
          div.style.opacity = "0";
          continue;
        }
        projected.set(position[i * 3]!, position[i * 3 + 1]!, position[i * 3 + 2]!).project(camera);
        const x = (projected.x * 0.5 + 0.5) * w;
        const y = (-projected.y * 0.5 + 0.5) * h;
        const r = radius(i);
        div.style.opacity = projected.z > 1 ? "0" : String(alpha[i]!);
        div.style.transform = `translate(${x + r * 0.7}px, ${y - r * 0.9}px) translate(-50%, -50%)`;
      }
      for (const i of badged) tag(i, "badge");
    }

    // Camera flights: to a channel, or back out to fit the rings in view.
    let flight: { from: THREE.Vector3; to: THREE.Vector3; fromTarget: THREE.Vector3; toTarget: THREE.Vector3; t: number } | null = null;
    function fly(to: THREE.Vector3, target: THREE.Vector3) {
      if (still) {
        camera.position.copy(to);
        controls.target.copy(target);
        return;
      }
      flight = { from: camera.position.clone(), to, fromTarget: controls.target.clone(), toTarget: target, t: 0 };
    }
    function fitView() {
      const shown = rings.filter((r) => r.step <= live.current.depth);
      const reach = (shown.at(-1)?.outer ?? 400) + 80;
      const fov = (camera.fov * Math.PI) / 180;
      const fit = reach / Math.tan(fov / 2) / Math.min(1, camera.aspect) * 0.92;
      const dir = camera.position.clone().sub(controls.target).setY(0).normalize();
      fly(new THREE.Vector3(dir.x * fit * 0.62, fit * 0.78, dir.z * fit * 0.62), new THREE.Vector3(0, -40, 0));
    }
    function focus(id: string | null) {
      selected = id ? index.get(id) ?? -1 : -1;
      controls.autoRotate = !still && selected < 0;
      refresh();
      if (selected < 0) return;
      const target = new THREE.Vector3(placed[selected]!.x, placed[selected]!.y, placed[selected]!.z);
      const dir = camera.position.clone().sub(controls.target).normalize();
      fly(target.clone().add(dir.multiplyScalar(420)), target);
    }
    let lastDepth = live.current.depth;
    api.current = {
      refresh: () => {
        refresh();
        if (live.current.depth !== lastDepth) {
          lastDepth = live.current.depth;
          if (selected < 0) fitView();
        }
      },
      focus,
    };

    function pick(ev: PointerEvent): number {
      const rect = renderer.domElement.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;
      let best = -1;
      let bestDepth = Infinity;
      for (let i = 0; i < count; i++) {
        if (alpha[i]! < 0.5) continue;
        projected.set(position[i * 3]!, position[i * 3 + 1]!, position[i * 3 + 2]!).project(camera);
        if (projected.z > 1) continue;
        const x = (projected.x * 0.5 + 0.5) * rect.width;
        const y = (-projected.y * 0.5 + 0.5) * rect.height;
        const r = Math.max(6, radius(i));
        if ((mx - x) ** 2 + (my - y) ** 2 <= r * r && projected.z < bestDepth) {
          best = i;
          bestDepth = projected.z;
        }
      }
      return best;
    }

    let downAt: [number, number] | null = null;
    const onMove = (ev: PointerEvent) => {
      const i = pick(ev);
      if (i !== hovered) {
        hovered = i;
        renderer.domElement.style.cursor = i >= 0 ? "pointer" : "grab";
        controls.autoRotate = !still && i < 0 && selected < 0;
        refresh();
      }
    };
    const onDown = (ev: PointerEvent) => {
      downAt = [ev.clientX, ev.clientY];
    };
    const onUp = (ev: PointerEvent) => {
      if (!downAt || Math.hypot(ev.clientX - downAt[0], ev.clientY - downAt[1]) > 4) return;
      const i = pick(ev);
      live.current.onSelect(i >= 0 ? nodes[i]!.id : null);
    };
    renderer.domElement.addEventListener("pointermove", onMove);
    renderer.domElement.addEventListener("pointerdown", onDown);
    renderer.domElement.addEventListener("pointerup", onUp);

    const resize = new ResizeObserver(() => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      material.uniforms.uScale!.value = h * 0.9 * renderer.getPixelRatio();
    });
    resize.observe(el);

    // The opening: each ring unfolds from the channels it hangs from.
    const born = performance.now();
    const delay = (i: number) => placed[i]!.ring * UNFOLD_STAGGER;
    let unfolding = true;
    const inward = [...nodes.keys()].sort((a, b) => placed[a]!.ring - placed[b]!.ring);
    function layoutAt(now: number) {
      const t = still ? Infinity : (now - born) / 1000;
      let moving = false;
      for (const i of inward) {
        const p = placed[i]!;
        const k = ease((t - delay(i)) / UNFOLD);
        if (k < 1) moving = true;
        const from = p.parent >= 0 ? point(p.parent) : { x: 0, y: 0, z: 0 };
        position[i * 3] = from.x + (p.x - from.x) * k;
        position[i * 3 + 1] = from.y + (p.y - from.y) * k;
        position[i * 3 + 2] = from.z + (p.z - from.z) * k;
      }
      tree.forEach(([a, b], k) => curve(point(a), point(b), SEGMENTS, treeAt, k * per * 3));
      treeGeometry.attributes.position!.needsUpdate = true;
      geometry.attributes.position!.needsUpdate = true;
      return moving;
    }

    let frame = 0;
    let lastAtlas = 0;
    fitView();
    function tick(now: number) {
      frame = requestAnimationFrame(tick);
      if (unfolding) unfolding = layoutAt(now);
      for (let i = 0; i < count; i++) {
        const shown = still || (now - born) / 1000 > delay(i) ? alphaTarget[i]! : 0;
        alpha[i] = still ? shown : alpha[i]! + (shown - alpha[i]!) * 0.12;
        lift[i] = still ? liftTarget[i]! : lift[i]! + (liftTarget[i]! - lift[i]!) * 0.18;
      }
      geometry.attributes.aAlpha!.needsUpdate = true;
      geometry.attributes.aLift!.needsUpdate = true;
      if (atlasDirty && now - lastAtlas > 250) {
        texture.needsUpdate = true;
        atlasDirty = false;
        lastAtlas = now;
        // The texture uploads during this frame's render, before the cells below are drawn.
        for (const i of drawn.splice(0)) cell[i] = i;
        geometry.attributes.aCell!.needsUpdate = true;
      }
      if (flight) {
        flight.t = Math.min(1, flight.t + 1 / 60);
        const k = ease(flight.t);
        camera.position.lerpVectors(flight.from, flight.to, k);
        controls.target.lerpVectors(flight.fromTarget, flight.toTarget, k);
        if (flight.t >= 1) flight = null;
      }
      controls.update();
      camera.updateMatrixWorld();
      sortByDepth();
      renderer.render(scene, camera);
      placeTags();
    }
    frame = requestAnimationFrame(tick);

    return () => {
      // Stop fetching avatars, so the next page's requests are not queued behind them.
      stopped = true;
      for (const img of loading) img.src = "";
      loading.clear();
      cancelAnimationFrame(frame);
      resize.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener("pointermove", onMove);
      renderer.domElement.removeEventListener("pointerdown", onDown);
      renderer.domElement.removeEventListener("pointerup", onUp);
      geometry.dispose();
      treeGeometry.dispose();
      focusGeometry.dispose();
      for (const g of guides) g.geometry.dispose();
      dust.dispose();
      material.dispose();
      texture.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      labels.replaceChildren();
      api.current = null;
    };
    // The scene is rebuilt only when the graph itself changes.
  }, [props.nodes, props.links, props.centre]);

  useEffect(() => {
    api.current?.refresh();
  }, [props.depth, props.dimmed, props.hidden, props.badges, props.badgeMin]);

  useEffect(() => {
    api.current?.focus(props.selected);
  }, [props.selected]);

  return (
    <div className="relative h-full w-full overflow-hidden">
      <div ref={host} className="absolute inset-0" />
      <div ref={overlay} className="pointer-events-none absolute inset-0" aria-hidden />
    </div>
  );
}
