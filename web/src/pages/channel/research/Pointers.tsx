import { useEffect, useState } from "react";

import { pointsTo, youtubeChannel } from "../../../api";
import { Empty, Loading } from "../../../components/ui";
import { count } from "../../../format";
import { attempt } from "../../../toasts";
import type { Pointer } from "../../../types";
import { useMap } from "../context";

export function Pointers() {
  const { m } = useMap();
  const [rows, setRows] = useState<Pointer[] | null>(null);
  useEffect(() => {
    setRows(null);
    void attempt(pointsTo(m.id)).then((r) => setRows(r?.rows ?? []));
  }, [m.id]);
  if (rows == null) return <Loading />;
  if (rows.length === 0) return <Empty title={`No mapped channel shows ${m.title} beside its videos yet`} body="This fills in as more neighbours are mapped." />;
  const real = rows.some((r) => r.real_views);
  return (
    <div className="flex flex-col gap-3">
      <p className="max-w-[85ch] text-sm text-ink-3">
        Channels whose viewers YouTube offers {m.title}.
        {real ? " Views sent come from your analytics. Beside is how often it appeared in that channel's recommendations." : " Beside is how often it appeared in that channel's recommendations."}
      </p>
      <table className="w-full table-fixed text-sm">
        <thead className="text-left text-xs text-ink-3">
          <tr>
            <th className="py-1 font-medium">Channel</th>
            {real && <th className="w-32 py-1 text-right font-medium">Views sent</th>}
            <th className="w-32 py-1 text-right font-medium">Beside its videos</th>
            <th className="w-20 py-1 text-right font-medium">Maps</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t border-line">
              <td className="truncate py-1.5 pr-2">
                <a href={youtubeChannel(r.id)} target="_blank" rel="noreferrer noopener" className="text-ink hover:underline">
                  {r.title}
                </a>
              </td>
              {real && <td className="py-1.5 text-right text-busy">{r.real_views ? count(r.real_views) : "–"}</td>}
              <td className="py-1.5 text-right text-ink-2">{r.coverage ? `${Math.round(r.coverage * 100)}%` : "–"}</td>
              <td className="py-1.5 text-right text-ink-3">{r.maps || "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
