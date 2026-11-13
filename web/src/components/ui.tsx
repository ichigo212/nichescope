import { X } from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  type AnchorHTMLAttributes,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
} from "react";

type Tone = "primary" | "secondary" | "ghost" | "danger";

const TONES: Record<Tone, string> = {
  primary: "bg-accent text-accent-ink hover:bg-accent-strong",
  secondary: "bg-overlay text-ink border border-line-strong hover:bg-hover hover:border-ink-3",
  ghost: "bg-transparent text-ink-2 hover:bg-hover hover:text-ink",
  danger: "bg-danger text-white hover:brightness-110",
};

export const buttonClass = (tone: Tone = "secondary", extra = "") =>
  "inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-sm px-3.5 text-sm font-semibold whitespace-nowrap " +
  "transition-[background-color,border-color,filter,transform] duration-150 ease-out-soft " +
  "active:scale-[.98] disabled:pointer-events-none disabled:opacity-40 " +
  TONES[tone] +
  " " +
  extra;

export function Button({
  tone = "secondary",
  icon,
  children,
  className = "",
  type = "button",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { tone?: Tone; icon?: ReactNode }) {
  return (
    <button type={type} {...rest} className={buttonClass(tone, className)}>
      {icon}
      {children}
    </button>
  );
}

/** A link that opens outside the app, in a new tab. */
export function OutLink({
  tone,
  icon,
  children,
  className = "",
  ...rest
}: AnchorHTMLAttributes<HTMLAnchorElement> & { tone?: Tone; icon?: ReactNode }) {
  return (
    <a target="_blank" rel="noreferrer noopener" {...rest} className={tone ? buttonClass(tone, className) : className}>
      {icon}
      {children}
    </a>
  );
}

export const FIELD =
  "h-9 rounded-sm border border-line-strong bg-raised px-3 text-sm text-ink " +
  "placeholder:text-ink-3 transition-[border-color,background-color] duration-150 " +
  "hover:border-ink-3 focus:border-accent focus:outline-none disabled:opacity-40";

export function Input({ icon, className = "", ...rest }: InputHTMLAttributes<HTMLInputElement> & { icon?: ReactNode }) {
  if (!icon) return <input {...rest} className={FIELD + " " + className} />;
  return (
    <label className={"relative flex items-center " + className}>
      <span className="pointer-events-none absolute left-3 text-ink-3">{icon}</span>
      <input {...rest} className={FIELD + " w-full pl-9"} />
    </label>
  );
}

export function TextArea({ className = "", ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...rest}
      className={
        "rounded-sm border border-line-strong bg-raised px-3 py-2 text-sm text-ink placeholder:text-ink-3 " +
        "transition-[border-color] duration-150 hover:border-ink-3 focus:border-accent focus:outline-none disabled:opacity-40 " +
        className
      }
    />
  );
}

/** A number box that only reports numbers. */
export function NumberInput({
  value,
  onChange,
  className = "",
  ...rest
}: Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange"> & { value: number; onChange: (v: number) => void }) {
  const [text, setText] = useState(String(value));
  useEffect(() => {
    setText(String(value));
  }, [value]);
  return (
    <input
      {...rest}
      type="number"
      value={text}
      onChange={(e) => {
        setText(e.target.value);
        const n = Number(e.target.value);
        if (e.target.value.trim() !== "" && Number.isFinite(n)) onChange(n);
      }}
      className={FIELD + " tabular-nums " + className}
    />
  );
}

export function Select({
  value,
  options,
  onChange,
  label,
  className = "",
  disabled,
}: {
  value: string;
  options: [string, string][];
  onChange: (v: string) => void;
  label: string;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <select aria-label={label} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} className={FIELD + " pr-8 " + className}>
      {options.map(([v, l]) => (
        <option key={v} value={v}>
          {l}
        </option>
      ))}
    </select>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return <span className={"inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent " + className} aria-hidden />;
}

type BadgeTone = "plain" | "accent" | "busy" | "danger" | "sync" | "api";
const BADGE: Record<BadgeTone, string> = {
  plain: "bg-overlay text-ink-2",
  accent: "bg-accent/15 text-accent",
  busy: "bg-busy/15 text-busy",
  danger: "bg-danger/15 text-danger",
  sync: "bg-sync/15 text-sync",
  api: "bg-api/15 text-api",
};

export function Badge({ tone = "plain", children, title }: { tone?: BadgeTone; children: ReactNode; title?: string }) {
  return (
    <span title={title} className={"inline-flex items-center gap-1 rounded-full px-2 py-px text-xs font-semibold " + BADGE[tone]}>
      {children}
    </span>
  );
}

/** One of a few, side by side. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex max-w-full flex-wrap rounded-sm border border-line-strong bg-raised p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={
            "h-8 rounded-[6px] px-3 text-sm font-semibold transition-colors duration-150 " +
            (o.value === value ? "bg-overlay text-ink shadow-sm" : "text-ink-3 hover:text-ink-2")
          }
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** On/off, as a role=switch button: one tab stop, Space flips it. */
export function Switch({
  checked,
  onChange,
  label,
  hint,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: ReactNode;
  hint?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <div className={"flex items-start gap-3 " + (disabled ? "opacity-40" : "")}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={"relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition-colors duration-150 " + (checked ? "bg-accent" : "bg-line-strong")}
      >
        <span
          className={
            "absolute top-0.5 size-4 rounded-full bg-ink shadow transition-[left] duration-150 ease-out-soft " + (checked ? "left-[18px]" : "left-0.5")
          }
        />
        <span className="sr-only">{typeof label === "string" ? label : "toggle"}</span>
      </button>
      <div className="min-w-0 cursor-default" onClick={() => !disabled && onChange(!checked)}>
        <p className="text-sm text-ink">{label}</p>
        {hint && <p className="mt-0.5 text-xs text-ink-3">{hint}</p>}
      </div>
    </div>
  );
}

/** A range with its value beside it. */
export function Slider({
  value,
  min,
  max,
  step = 1,
  onChange,
  label,
  format = (v) => String(v),
}: {
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
  label: string;
  format?: (v: number) => string;
}) {
  return (
    <div className="flex items-center gap-3">
      <input
        type="range"
        aria-label={label}
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1.5 flex-1 cursor-pointer accent-[var(--color-accent)]"
      />
      <span className="w-14 text-right text-sm text-ink-2 tabular-nums">{format(value)}</span>
    </div>
  );
}

/** A titled group. `aside` sits right of the title. */
export function Section({
  title,
  hint,
  aside,
  children,
  className = "",
}: {
  title: ReactNode;
  hint?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={"rounded-lg border border-line bg-raised p-5 " + className}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-ink">{title}</h2>
          {hint && <p className="mt-1 text-sm text-ink-3">{hint}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

/** A label, a control, and a line under it. */
export function Field({ label, hint, children, className = "" }: { label: ReactNode; hint?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <label className={"flex min-w-0 flex-col gap-1.5 " + className}>
      <span className="text-xs font-semibold text-ink-2">{label}</span>
      {children}
      {hint && <span className="text-xs text-ink-3">{hint}</span>}
    </label>
  );
}

/** Nothing to show yet, and what to do about it. */
export function Empty({ title, body, action }: { title: ReactNode; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className="grid place-items-center rounded-lg border border-dashed border-line-strong p-12 text-center">
      <div className="max-w-md">
        <p className="text-lg font-semibold text-ink">{title}</p>
        {body && <p className="mt-1.5 text-sm text-ink-3">{body}</p>}
        {action && <div className="mt-5 flex justify-center gap-2">{action}</div>}
      </div>
    </div>
  );
}

export function Loading({ text = "Loading" }: { text?: string }) {
  return (
    <p className="flex items-center gap-2 py-10 text-sm text-ink-3" aria-live="polite">
      <Spinner className="size-3.5" />
      {text}
    </p>
  );
}

export function Avatar({ src, size = "size-7", className = "" }: { src: string | null | undefined; size?: string; className?: string }) {
  return src ? (
    <img src={src} alt="" loading="lazy" referrerPolicy="no-referrer" className={`${size} shrink-0 rounded-full bg-overlay object-cover ${className}`} />
  ) : (
    <span className={`${size} shrink-0 rounded-full bg-overlay ${className}`} />
  );
}

/** A modal panel. Escape and the backdrop close it. */
export function Dialog({
  open,
  title,
  onClose,
  children,
  wide = false,
}: {
  open: boolean;
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onMouseDown={(e) => e.target === ref.current && onClose()}
      className={
        (wide ? "w-[min(92vw,720px)] " : "w-[min(92vw,520px)] ") +
        "m-auto rounded-lg border border-line-strong bg-raised p-0 text-ink shadow-2xl backdrop:bg-black/60 backdrop:backdrop-blur-[2px]"
      }
    >
      {open && (
        <div className="flex flex-col gap-4 p-6">
          <div className="flex items-start justify-between gap-4">
            <h2 className="text-lg font-semibold text-ink">{title}</h2>
            <button type="button" aria-label="Close" className="rounded-sm p-1 text-ink-3 hover:bg-hover hover:text-ink" onClick={onClose}>
              <X className="size-4" />
            </button>
          </div>
          {children}
        </div>
      )}
    </dialog>
  );
}

/** Copy text to the clipboard, saying so for a moment. */
export function CopyButton({ text, label = "Copy", className = "" }: { text: string; label?: string; className?: string }) {
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!done) return;
    const t = setTimeout(() => setDone(false), 1500);
    return () => clearTimeout(t);
  }, [done]);
  return (
    <Button
      tone="ghost"
      className={"h-8 px-2.5 " + className}
      onClick={() => void navigator.clipboard.writeText(text).then(() => setDone(true))}
    >
      {done ? "Copied" : label}
    </Button>
  );
}

/** A yes or no question in an in-app dialog. */
export function ConfirmDialog({
  open,
  title,
  body,
  yes,
  danger = false,
  onYes,
  onClose,
}: {
  open: boolean;
  title: ReactNode;
  body: ReactNode;
  yes: string;
  danger?: boolean;
  onYes: () => void;
  onClose: () => void;
}) {
  return (
    <Dialog open={open} title={title} onClose={onClose}>
      <div className="text-sm text-ink-2">{body}</div>
      <div className="flex justify-end gap-2">
        <Button tone="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button
          tone={danger ? "danger" : "primary"}
          onClick={() => {
            onClose();
            onYes();
          }}
        >
          {yes}
        </Button>
      </div>
    </Dialog>
  );
}
