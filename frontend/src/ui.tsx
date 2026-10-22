import type { ReactNode } from "react";
import { motion, useReducedMotion } from "motion/react";
import {
  ArrowsClockwise, Cpu, LockKey, Prohibit, Question, Rows, Stack,
} from "@phosphor-icons/react";

export const SPRING = [0.32, 0.72, 0, 1] as const;

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

/** Pick an icon for an example question from its topic words. */
export function topicIcon(q: string) {
  const s = q.toLowerCase();
  if (s.includes("deadlock")) return Prohibit;
  if (s.includes("bakery") || s.includes("critical section") || s.includes("semaphore")) return LockKey;
  if (s.includes("round robin") || s.includes("scheduling")) return ArrowsClockwise;
  if (s.includes("process control")) return Cpu;
  if (s.includes("fit") || s.includes("memory") || s.includes("paging")) return Rows;
  if (s.includes("kernel")) return Stack;
  return Question;
}

/** Fade-up entrance. Staggers by `index`; static under reduced motion. */
export function Rise({ children, index = 0, className, as = "div" }: {
  children: ReactNode; index?: number; className?: string; as?: "div" | "section" | "li";
}) {
  const reduce = useReducedMotion();
  const M = motion[as];
  return (
    <M
      className={className}
      initial={reduce ? false : { opacity: 0, y: 18, filter: "blur(6px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      transition={{ duration: 0.75, delay: 0.06 * index, ease: SPRING }}
    >
      {children}
    </M>
  );
}

/** Double-bezel container: outer shell (tray) + inner core (plate). */
export function Card({ children, className, coreClassName, id }: {
  children: ReactNode; className?: string; coreClassName?: string; id?: string;
}) {
  return (
    <div id={id} className={cx("shell", className)}>
      <div className={cx("core h-full", coreClassName ?? "p-5 md:p-6")}>{children}</div>
    </div>
  );
}

export function Segmented<T extends string>({ value, options, onChange, label, labels }: {
  value: T; options: readonly T[]; onChange: (v: T) => void; label: string; labels: Record<T, string>;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-full bg-muted p-1 ring-1 ring-line">
      {options.map((o) => (
        <button
          key={o}
          type="button"
          role="radio"
          aria-checked={value === o}
          onClick={() => onChange(o)}
          className={cx(
            "rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-all duration-300 ease-spring",
            value === o ? "bg-core text-accent-text shadow-float ring-1 ring-line" : "text-ink-3 hover:text-ink",
          )}
        >
          {labels[o]}
        </button>
      ))}
    </div>
  );
}

export function Toggle({ checked, onChange, label, hint }: {
  checked: boolean; onChange: (v: boolean) => void; label: string; hint?: string;
}) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2.5 text-[13px] text-ink-2 select-none" title={hint}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cx(
          "relative h-5 w-9 shrink-0 rounded-full ring-1 ring-line transition-colors duration-300 ease-spring",
          checked ? "bg-accent" : "bg-muted",
        )}
      >
        <span
          className={cx(
            "absolute top-[3px] left-[3px] h-[14px] w-[14px] rounded-full bg-core shadow transition-transform duration-300 ease-spring",
            checked && "translate-x-4",
          )}
        />
      </button>
      {label}
    </label>
  );
}

export function Badge({ children, tone = "neutral", icon: Icon }: {
  children: ReactNode; tone?: "neutral" | "accent"; icon?: React.ElementType;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-[8px] px-2 py-1 text-[12px] font-medium",
        tone === "accent" ? "bg-accent-soft text-accent-text" : "bg-muted text-ink-2 ring-1 ring-line",
      )}
    >
      {Icon && <Icon size={13} weight="bold" />}
      {children}
    </span>
  );
}

export function IconTile({ icon: Icon, accent = false }: { icon: React.ElementType; accent?: boolean }) {
  return (
    <span className={cx(
      "grid h-9 w-9 shrink-0 place-items-center rounded-[12px] ring-1",
      accent ? "bg-accent text-accent-ink ring-transparent" : "bg-muted text-ink-2 ring-line",
    )}>
      <Icon size={18} weight={accent ? "bold" : "light"} />
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("shimmer rounded-[12px]", className)} />;
}

export function Empty({ icon, title, children }: { icon: React.ElementType; title: string; children?: ReactNode }) {
  return (
    <Card coreClassName="flex flex-col items-start gap-4 px-6 py-10 md:px-8">
      <IconTile icon={icon} accent />
      <div>
        <p className="text-[17px] font-semibold tracking-tight text-ink">{title}</p>
        {children && <div className="mt-1.5 max-w-[60ch] text-[15px] leading-relaxed text-ink-3">{children}</div>}
      </div>
    </Card>
  );
}

export function PageTitle({ title, sub }: { title: string; sub?: string }) {
  return (
    <Rise className="mb-8 md:mb-10">
      <h1 className="text-[34px] leading-[1.05] font-semibold tracking-[-0.035em] text-ink md:text-[46px]">{title}</h1>
      {sub && <p className="mt-3 max-w-[60ch] text-[16px] leading-relaxed text-ink-3">{sub}</p>}
    </Rise>
  );
}
