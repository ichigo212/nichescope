import { Download, Network } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { deepenMap, exportUrl, removeMap, updateSettings } from "../../api";
import { Button, Field, NumberInput, Section, Select, Switch, TextArea, buttonClass } from "../../components/ui";
import { runJob } from "../../events";
import { ago, plural } from "../../format";
import { attempt, toast } from "../../toasts";
import { useMap, useMapChange } from "./context";

export function SettingsTab() {
  const { m, busy } = useMap();
  const change = useMapChange();
  const navigate = useNavigate();
  const st = m.settings;
  const top = m.limits;
  const [topics, setTopics] = useState(st.topics);
  const [titles, setTitles] = useState(st.titles);
  const [instructions, setInstructions] = useState(st.instructions);
  const [steps, setSteps] = useState("1");
  const [sure, setSure] = useState(false);
  useEffect(() => {
    setTopics(st.topics);
    setTitles(st.titles);
    setInstructions(st.instructions);
  }, [m.id, st.topics, st.titles, st.instructions]);
  const changed = topics !== st.topics || titles !== st.titles || instructions !== st.instructions;
  const fits = topics >= 1 && topics <= top.topics && titles >= 1 && titles <= top.titles && instructions.length <= top.instructions;

  return (
    <div className="mx-auto flex w-full max-w-[720px] flex-col gap-5">
      <Section title="Topics" hint="Used every time topics are generated for this channel.">
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            void change(updateSettings(m.id, { topics, titles, instructions })).then((ok) => ok && toast("Settings saved"));
          }}
        >
          <div className="flex flex-wrap gap-4">
            <Field label={`Topics per run (1–${top.topics})`}>
              <NumberInput className="w-28" min={1} max={top.topics} value={topics} onChange={setTopics} />
            </Field>
            <Field label={`Titles per topic (1–${top.titles})`}>
              <NumberInput className="w-28" min={1} max={top.titles} value={titles} onChange={setTitles} />
            </Field>
          </div>
          <Field label={`Standing instructions (${instructions.length} of ${top.instructions})`} hint="Sent with every run, for example: no romance, finished stories only.">
            <TextArea rows={4} maxLength={top.instructions} value={instructions} onChange={(e) => setInstructions(e.target.value)} />
          </Field>
          <div className="flex items-center gap-3">
            <Button type="submit" tone="primary" disabled={!changed || !fits}>
              Save
            </Button>
            {!fits && (
              <span className="text-xs text-danger">
                Topics are 1 to {top.topics}, titles 1 to {top.titles}.
              </span>
            )}
          </div>
        </form>
        <div className="mt-5 flex flex-col gap-4 border-t border-line pt-4">
          <Switch
            checked={st.check_youtube}
            onChange={(on) => void change(updateSettings(m.id, { check_youtube: on }))}
            label="Check topics on YouTube"
            hint="Searches YouTube for each topic and flags one a recent video already covers."
          />
          <Switch
            checked={st.read_descriptions}
            onChange={(on) => void change(updateSettings(m.id, { read_descriptions: on }))}
            label="Read video descriptions"
            hint="Gives the breakouts' descriptions to topics and answers, not only their titles."
          />
        </div>
      </Section>

      <Section title="The map" hint={`${plural(m.expanded.length, "channel")} mapped around, ${plural(m.videosRead, "video")} of this channel read, updated ${ago(m.scannedAt)}.`}>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Map further out">
            <Select
              label="Steps"
              value={steps}
              onChange={setSteps}
              options={[1, 2, 3, 4, 5].map((n): [string, string] => [String(n), `${n} step${n === 1 ? "" : "s"}`])}
            />
          </Field>
          <Button icon={<Network className="size-4" />} disabled={busy} onClick={() => void runJob(deepenMap(m.id, Number(steps)))}>
            Map further out
          </Button>
        </div>
        <p className="mt-2 text-xs text-ink-3">Each step reads the neighbours of the channels already found. It takes a few minutes.</p>
        <div className="mt-5 flex flex-wrap gap-2 border-t border-line pt-4">
          <a href={exportUrl(m.id, "channels")} download className={buttonClass("secondary")}>
            <Download className="size-4" />
            Export channels CSV
          </a>
          <a href={exportUrl(m.id, "breakouts")} download className={buttonClass("secondary")}>
            <Download className="size-4" />
            Export breakouts CSV
          </a>
        </div>
      </Section>

      <section className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-danger/40 p-5">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-ink">Remove this map</h2>
          <p className="mt-1 text-sm text-ink-3">It leaves the channel list. The file is kept and can be restored from the home page.</p>
        </div>
        <Button
          tone={sure ? "danger" : "secondary"}
          onClick={() => {
            if (!sure) return setSure(true);
            void attempt(removeMap(m.id)).then((ok) => {
              if (!ok) return;
              toast(`Removed ${m.title}`);
              navigate("/");
            });
          }}
        >
          {sure ? "Click again to remove" : "Remove map"}
        </Button>
      </section>
    </div>
  );
}
