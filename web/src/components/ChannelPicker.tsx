import { Search } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { suggestChannels } from "../api";
import type { ChannelSuggestion } from "../types";
import { Avatar, Button, Input, Spinner } from "./ui";

/** A channel name box with suggestions from YouTube as you type. */
export function ChannelPicker({
  label,
  action,
  actionIcon,
  disabled,
  onPick,
  className = "",
}: {
  label: string;
  action: string;
  actionIcon?: ReactNode;
  disabled?: boolean;
  onPick: (channel: string, title?: string) => void;
  className?: string;
}) {
  const [text, setText] = useState("");
  const [rows, setRows] = useState<ChannelSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [looking, setLooking] = useState(false);
  const box = useRef<HTMLFormElement>(null);

  useEffect(() => {
    const q = text.trim();
    // A link, @handle or channel id already says which channel it is.
    if (q.length < 2 || /youtube\.com|youtu\.be|^@|^UC[\w-]{22}$/.test(q)) {
      setRows([]);
      setLooking(false);
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      setLooking(true);
      suggestChannels(q, ctrl.signal)
        .then((r) => {
          setRows(r);
          setActive(-1);
          setOpen(true);
        })
        .catch(() => setRows([]))
        .finally(() => !ctrl.signal.aborted && setLooking(false));
    }, 350);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [text]);

  useEffect(() => {
    const away = (e: MouseEvent) => box.current && !box.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, []);

  const pick = (channel: string, title?: string) => {
    setText("");
    setRows([]);
    setOpen(false);
    onPick(channel, title);
  };

  return (
    <form
      ref={box}
      className={"relative flex min-w-0 items-center gap-2 " + className}
      onSubmit={(e) => {
        e.preventDefault();
        const row = active >= 0 ? rows[active] : undefined;
        if (row) pick(row.id, row.title);
        else if (text.trim()) pick(text.trim());
      }}
    >
      <Input
        className="min-w-0 flex-1"
        icon={looking ? <Spinner className="size-3.5" /> : <Search className="size-4" />}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onFocus={() => rows.length && setOpen(true)}
        onKeyDown={(e) => {
          if (!open || !rows.length) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((i) => Math.min(rows.length - 1, i + 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((i) => Math.max(-1, i - 1));
          } else if (e.key === "Escape") setOpen(false);
        }}
        placeholder={label}
        aria-label={label}
        aria-autocomplete="list"
        aria-expanded={open && rows.length > 0}
      />
      <Button type="submit" tone="primary" icon={actionIcon} disabled={disabled || !text.trim()}>
        {action}
      </Button>
      {open && rows.length > 0 && (
        <ul role="listbox" className="absolute top-10 left-0 z-30 flex w-full max-w-xl flex-col rounded-md border border-line-strong bg-overlay p-1 shadow-xl">
          {rows.map((r, i) => (
            <li key={r.id} role="option" aria-selected={i === active}>
              <button
                type="button"
                className={"flex w-full items-center gap-2.5 rounded-sm px-2 py-1.5 text-left hover:bg-hover " + (i === active ? "bg-hover" : "")}
                onClick={() => pick(r.id, r.title)}
              >
                <Avatar src={r.avatar} />
                <span className="min-w-0 flex-1 truncate text-sm text-ink">{r.title}</span>
                <span className="truncate text-xs text-ink-3">{r.detail}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
