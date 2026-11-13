import { FlaskConical } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { getStudy, runStudy } from "../../api";
import { Button, Empty, Loading, Section } from "../../components/ui";
import { VideoCard } from "../../components/VideoCard";
import { runJob, useJobEvents } from "../../events";
import { ago, count, percent, times } from "../../format";
import { attempt } from "../../toasts";
import type { Study, StudyStyle } from "../../types";
import { useMap } from "./context";

export function StudyTab() {
  const { m, busy } = useMap();
  const [study, setStudy] = useState<Study | null | undefined>(undefined);
  const load = useCallback(() => void attempt(getStudy(m.id)).then((r) => r && setStudy(r.study)), [m.id]);
  useEffect(load, [load]);
  useJobEvents((e) => e.job.kind === "study" && e.job.status === "done" && load());

  const start = (
    <Button icon={<FlaskConical className="size-4" />} disabled={busy} onClick={() => void runJob(runStudy(m.id))}>
      {study ? "Study again" : "Study the competitors"}
    </Button>
  );
  if (study === undefined) return <Loading />;
  if (study === null) {
    return (
      <Empty
        title="No study yet"
        body="A study reads the near competitors on this map and compares their best and worst videos with yours: title habits, thumbnail styles and how soon small channels broke out. It takes a few minutes."
        action={start}
      />
    );
  }

  const habits = study.titles.filter((t) => t.up + t.down > 0).sort((a, b) => b.up - b.down - (a.up - a.down));
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-ink">What the channels around {m.title} do differently</h2>
          <p className="mt-1 text-sm text-ink-3">
            {count(study.videos)} videos from {study.channels} near competitors, each against its own channel's usual · studied {ago(study.at)}
            {study.stale && <span className="text-busy"> · due for a refresh</span>}
          </p>
        </div>
        {start}
      </div>

      {study.findings.length > 0 && (
        <ol className="flex flex-col gap-3">
          {study.findings.map((f) => (
            <li key={f.key} className="rounded-lg border border-line bg-raised p-4">
              <h3 className="text-base font-semibold text-ink">{f.title}</h3>
              <p className="mt-1.5 text-sm text-ink-2">{f.finding}</p>
              <p className="mt-1.5 text-sm text-ink">{f.action}</p>
              <p className="mt-2 text-xs text-ink-3">{f.basis}</p>
            </li>
          ))}
        </ol>
      )}

      <Section title="Title habits" hint={`How often each appears, and how those videos did against their own channel's usual. "Ours" is your last ${study.recentTitles} titles.`}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="text-left text-xs text-ink-3">
              <tr>
                <th className="py-1 font-medium">Habit</th>
                <th className="w-20 py-1 text-right font-medium">Theirs</th>
                <th className="w-20 py-1 text-right font-medium">Ours</th>
                <th className="w-24 py-1 text-right font-medium">With it</th>
                <th className="w-24 py-1 text-right font-medium">Without</th>
                <th className="w-36 py-1 pl-4 font-medium">Channels better / worse</th>
              </tr>
            </thead>
            <tbody>
              {habits.map((t) => (
                <tr key={t.key} className="border-t border-line">
                  <td className="py-1.5 text-ink">{t.label}</td>
                  <td className="py-1.5 text-right text-ink-2">{percent(t.share)}</td>
                  <td className="py-1.5 text-right text-ink-2">{t.ours == null ? "?" : percent(t.ours)}</td>
                  <td className="py-1.5 text-right text-ink-2">{t.with == null ? "?" : times(t.with)}</td>
                  <td className="py-1.5 text-right text-ink-2">{t.without == null ? "?" : times(t.without)}</td>
                  <td className="py-1.5 pl-4">
                    <span className={t.up > t.down ? "text-accent" : t.down > t.up ? "text-danger" : "text-ink-3"}>
                      {t.up} / {t.down}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {study.rising.length > 0 && (
          <p className="mt-3 text-xs text-ink-3">
            Used more lately: {study.rising.map((r) => `${r.label.toLowerCase()} (${percent(r.was)} to ${percent(r.now)})`).join(", ")}.
          </p>
        )}
      </Section>

      {(study.styles.winners || study.styles.ours) && (
        <Section title="Thumbnails" hint="Labelled by the vision model: each competitor's four best and four worst videos, and your latest.">
          <StyleTable rows={study.styleRows} styles={study.styles} />
        </Section>
      )}

      {study.escapes.length > 0 && (
        <Section title="How soon small channels broke out" hint="The smallest competitors, oldest video first: the first video to reach 10,000 views.">
          <ul className="flex flex-col gap-1.5 text-sm">
            {study.escapes.map((e) => (
              <li key={e.channel} className="flex flex-wrap items-baseline justify-between gap-x-4 border-t border-line pt-1.5 first:border-t-0 first:pt-0">
                <span className="text-ink">{e.channel}</span>
                <span className="text-ink-2">
                  {e.hit ? `video ${e.hit} of ${e.videos}${e.days ? `, after ${e.days} days` : ""}: ${e.title} (${count(e.views)} views)` : `not yet, after ${e.videos} videos`}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Their best this year">
          <div className="grid grid-cols-2 gap-x-3 gap-y-5">
            {study.theirBest.slice(0, 6).map((v) => (
              <VideoCard key={v.id} v={v} />
            ))}
          </div>
        </Section>
        <Section title="Your latest">
          <div className="grid grid-cols-2 gap-x-3 gap-y-5">
            {study.yourLatest.slice(0, 6).map((v) => (
              <VideoCard key={v.id} v={v} />
            ))}
          </div>
        </Section>
      </div>
    </div>
  );
}

function StyleTable({ rows, styles }: { rows: Study["styleRows"]; styles: Study["styles"] }) {
  const columns: [string, StudyStyle | null][] = [
    ["Their best", styles.winners],
    ["Their worst", styles.losers],
    ["Yours", styles.ours],
  ];
  const lines: [string, (s: StudyStyle) => string][] = [
    ...rows.map((r): [string, (s: StudyStyle) => string] => [r.label, (s) => percent(s[r.key] as number)]),
    ["Bright background", (s) => percent(s.bright)],
    ["Dark background", (s) => percent(s.dark)],
    ["Faces on average", (s) => String(s.faces)],
    ["Words of text on average", (s) => String(s.words)],
  ];
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-sm">
        <thead className="text-left text-xs text-ink-3">
          <tr>
            <th className="py-1 font-medium" />
            {columns.map(([label, s]) => (
              <th key={label} className="w-28 py-1 text-right font-medium">
                {label}
                {s && <span className="block font-normal">{s.n} thumbnails</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lines.map(([label, show]) => (
            <tr key={label} className="border-t border-line">
              <td className="py-1.5 text-ink">{label}</td>
              {columns.map(([key, s]) => (
                <td key={key} className="py-1.5 text-right text-ink-2">
                  {s ? show(s) : "?"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
