import type { Card } from "../types";

/** A mapped channel's small radial map: it in the middle, its nearest around it. */
export function MiniMap({ c }: { c: Card }) {
  const size = 132;
  const mid = size / 2;
  const rings = [30, 52];
  const per = [0, 0];
  c.dots.forEach((d) => (per[d.ring] = (per[d.ring] ?? 0) + 1));
  const seen = [0, 0];
  const clip = `mini-disc-${c.id}`;
  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="size-[132px]" aria-hidden="true">
      <defs>
        <radialGradient id={`glow-${c.id}`}>
          <stop offset="0%" stopColor="var(--color-sync)" stopOpacity={0.28} />
          <stop offset="100%" stopColor="var(--color-sync)" stopOpacity={0} />
        </radialGradient>
        <clipPath id={clip} clipPathUnits="objectBoundingBox">
          <circle cx="0.5" cy="0.5" r="0.5" />
        </clipPath>
      </defs>
      <circle cx={mid} cy={mid} r={mid - 2} fill={`url(#glow-${c.id})`} />
      {rings.map((r) => (
        <circle key={r} cx={mid} cy={mid} r={r} fill="none" className="stroke-sync/25" strokeWidth={1} />
      ))}
      {c.dots.map((d, i) => {
        const k = seen[d.ring]!++;
        const a = (k / Math.max(1, per[d.ring]!)) * Math.PI * 2 + (d.ring ? 0.3 : 0);
        const r = rings[d.ring]!;
        const x = mid + Math.cos(a) * r;
        const y = mid + Math.sin(a) * r;
        return (
          <g key={i}>
            <line x1={mid} y1={mid} x2={x} y2={y} className="stroke-sync/20" strokeWidth={0.8} />
            {d.avatar ? <image href={d.avatar} x={x - 7} y={y - 7} width={14} height={14} clipPath={`url(#${clip})`} /> : <circle cx={x} cy={y} r={6} className="fill-overlay" />}
          </g>
        );
      })}
      {c.avatar ? (
        <image href={c.avatar} x={mid - 13} y={mid - 13} width={26} height={26} clipPath={`url(#${clip})`} />
      ) : (
        <circle cx={mid} cy={mid} r={13} className="fill-raised" />
      )}
      <circle cx={mid} cy={mid} r={13} fill="none" className="stroke-ink/70" strokeWidth={1.5} />
    </svg>
  );
}
