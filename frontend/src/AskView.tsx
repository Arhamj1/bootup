import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  ArrowLeft, ArrowRight, ArrowUp, BookOpenText, Books, Brain, FunnelSimple, MagnifyingGlass, Quotes,
  SlidersHorizontal, Stop, WarningCircle,
} from "@phosphor-icons/react";
import { MODE_HELP, MODE_LABEL, getStats, type AskOptions, type Mode, type Status, type Turn } from "./api";
import { Markdown, SourceCard } from "./Answer";
import { Badge, Card, IconTile, Rise, SPRING, Segmented, Skeleton, Toggle, cx, topicIcon } from "./ui";

interface AskProps {
  status: Status | null;
  turn: Turn | null;
  options: AskOptions;
  setOptions: (o: AskOptions) => void;
  onAsk: (q: string) => void;
  onStop: () => void;
  onHome: () => void;
  busy: boolean;
}

export function AskView(props: AskProps) {
  const { turn } = props;
  return (
    <AnimatePresence mode="wait">
      {turn ? (
        <motion.div key="conversation" exit={{ opacity: 0 }} transition={{ duration: 0.2 }} className="pb-56">
          <button type="button" onClick={props.onHome}
            className="group mb-6 inline-flex items-center gap-2 text-[13px] text-ink-3 transition-colors hover:text-ink">
            <ArrowLeft size={15} className="transition-transform duration-300 ease-spring group-hover:-translate-x-0.5" />
            Start page
          </button>
          <TurnView key={turn.id} turn={turn} />
          <Dock {...props} />
        </motion.div>
      ) : (
        <motion.div key="home" exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
          <Home {...props} />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ------------------------------------------------------------------ Start page */
function Home({ status, options, setOptions, onAsk, busy }: AskProps) {
  return (
    <div className="flex flex-col gap-16 md:gap-24">
      <section className="grid items-start gap-10 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] lg:gap-14">
        <div className="pt-2 lg:pt-8">
          <Rise>
            <span className="inline-flex items-center gap-2 rounded-full bg-accent-soft px-3 py-1 text-[12px] font-medium text-accent-text">
              <Books size={14} weight="bold" /> {status?.course ?? "Operating Systems"}
            </span>
          </Rise>
          <Rise index={1}>
            <h1 className="mt-5 text-[44px] leading-[0.98] font-semibold tracking-[-0.045em] text-ink md:text-[64px]">
              Revise from your <span className="text-accent-text">own slides.</span>
            </h1>
          </Rise>
          <Rise index={2}>
            <p className="mt-5 max-w-[46ch] text-[17px] leading-relaxed text-ink-3">
              Ask anything from the course. Every answer cites the slide or page it came from.
            </p>
          </Rise>
          <Rise index={3} className="mt-9">
            <Composer big options={options} setOptions={setOptions} onAsk={onAsk} busy={busy} />
          </Rise>
        </div>

        <div className="lg:pt-8">
          <Rise index={2}>
            <p className="mb-4 text-[13px] font-medium text-ink-3">Start with a question from your slides</p>
          </Rise>
          <ul className="flex flex-col gap-2.5">
            {(status?.examples ?? []).map((q, i) => {
              const Icon = topicIcon(q);
              return (
                <Rise as="li" key={q} index={3 + i}>
                  <button type="button" disabled={busy} onClick={() => onAsk(q)}
                    className="group shell w-full !p-1 text-left transition-transform duration-500 ease-spring hover:-translate-y-0.5 active:scale-[0.99] disabled:opacity-50">
                    <span className="core flex items-center gap-3.5 px-3.5 py-3">
                      <IconTile icon={Icon} />
                      <span className="flex-1 text-[14px] leading-snug text-ink-2 transition-colors group-hover:text-ink">{q}</span>
                      <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-muted text-ink-3 transition-all duration-500 ease-spring group-hover:translate-x-0.5 group-hover:bg-accent group-hover:text-accent-ink">
                        <ArrowRight size={13} weight="bold" />
                      </span>
                    </span>
                  </button>
                </Rise>
              );
            })}
            {!status && [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[62px] rounded-[28px]" />)}
          </ul>
        </div>
      </section>

      <IndexBento status={status} />
    </div>
  );
}

/** Real numbers from the last index build, laid out as an asymmetric bento. */
function IndexBento({ status }: { status: Status | null }) {
  const [stats, setStats] = useState<Record<string, any> | null>(null);
  useEffect(() => { getStats().then(setStats).catch(() => setStats(null)); }, [status?.chunks]);
  if (!stats) return null;
  const topics = Object.entries(stats.chunks_by_topic as Record<string, number>).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...topics.map(([, n]) => n));
  const files = stats.files_by_source_type ?? {};
  return (
    <section>
      <Rise><h2 className="text-[24px] font-semibold tracking-[-0.025em] text-ink md:text-[28px]">What BootUp searches</h2></Rise>
      <div className="mt-6 grid gap-4 md:grid-cols-[1.35fr_1fr] md:grid-rows-3">
        <Rise index={1} className="md:row-span-3">
          <Card className="h-full" coreClassName="flex h-full flex-col p-6 md:p-8">
            <p className="text-[13px] text-ink-3">Passages indexed</p>
            <p className="mt-1 font-mono text-[52px] leading-none font-semibold tracking-[-0.04em] text-ink tabular-nums">{stats.chunks_indexed}</p>
            <p className="mt-2 text-[14px] text-ink-3">from {stats.files_used} files, {stats.duplicates_dropped} near-duplicates dropped</p>
            <ul className="mt-8 flex flex-col gap-2.5">
              {topics.map(([t, n]) => (
                <li key={t} className="grid grid-cols-[112px_1fr_40px] items-center gap-3 text-[13px]">
                  <span className="truncate text-ink-2">{t}</span>
                  <span className="h-1.5 rounded-full bg-accent/75" style={{ width: `${Math.max(4, (n / max) * 100)}%` }} />
                  <span className="text-right font-mono text-ink-3 tabular-nums">{n}</span>
                </li>
              ))}
            </ul>
          </Card>
        </Rise>
        <Rise index={2}>
          <Card className="h-full" coreClassName="flex h-full items-center gap-4 p-5 md:p-6">
            <IconTile icon={Books} accent />
            <div>
              <p className="font-mono text-[28px] leading-none font-semibold text-ink tabular-nums">{files.course ?? "-"}</p>
              <p className="mt-1 text-[13px] text-ink-3">course files: slides, notes and textbook chapters{files.open ? `, plus ${files.open} open resources` : ""}</p>
            </div>
          </Card>
        </Rise>
        <Rise index={3}>
          <div className="h-full rounded-[28px] bg-accent p-6 text-accent-ink">
            <FunnelSimple size={22} weight="bold" />
            <p className="mt-3 text-[16px] leading-snug font-semibold">Hybrid search</p>
            <p className="mt-1 text-[13px] leading-relaxed opacity-80">Meaning-based and keyword search, merged with Reciprocal Rank Fusion.</p>
          </div>
        </Rise>
        <Rise index={4}>
          <Card className="h-full" coreClassName="flex h-full items-center gap-4 p-5 md:p-6">
            <IconTile icon={Brain} />
            <div className="min-w-0">
              <p className="truncate font-mono text-[15px] font-medium text-ink">{status?.llm_model ?? "-"}</p>
              <p className="mt-1 text-[13px] text-ink-3">writes answers only from the passages it is given</p>
            </div>
          </Card>
        </Rise>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ Composer */
function Composer({ big = false, options, setOptions, onAsk, onStop, busy }: {
  big?: boolean; options: AskOptions; setOptions: (o: AskOptions) => void;
  onAsk: (q: string) => void; onStop?: () => void; busy: boolean;
}) {
  const [draft, setDraft] = useState("");
  const [showOpts, setShowOpts] = useState(big);
  const submit = () => {
    const text = draft.trim();
    if (!text || busy) return;
    onAsk(text);
    setDraft("");
  };
  return (
    <div className={cx(big ? "shell" : "glass rounded-[28px] p-1.5")}>
      <form className="core p-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <div className="flex items-end gap-2">
          <label htmlFor={big ? "question" : "followup"} className="sr-only">Question</label>
          <textarea
            id={big ? "question" : "followup"}
            rows={1}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
            placeholder={big ? "What happens when a process requests a resource held by another?" : "Ask another question"}
            className={cx(
              "flex-1 resize-none bg-transparent px-3.5 text-ink outline-none [field-sizing:content] placeholder:text-ink-3",
              big ? "max-h-[220px] min-h-[64px] py-3.5 text-[17px]" : "max-h-[160px] min-h-[44px] py-2.5 text-[15px]",
            )}
          />
          {busy && onStop ? (
            <button type="button" onClick={onStop} aria-label="Stop"
              className="mb-1 mr-1 grid h-10 w-10 shrink-0 place-items-center rounded-full bg-ink text-bg active:scale-[0.96]">
              <Stop size={15} weight="fill" />
            </button>
          ) : (
            <button type="submit" disabled={!draft.trim() || busy}
              className="group mb-1 mr-1 inline-flex h-10 shrink-0 items-center gap-2 rounded-full bg-accent pr-1 pl-4 text-[14px] font-medium text-accent-ink transition-all duration-500 ease-spring active:scale-[0.97] disabled:opacity-35">
              Ask
              <span className="grid h-8 w-8 place-items-center rounded-full bg-black/10 transition-transform duration-500 ease-spring group-hover:-translate-y-[1px] group-hover:translate-x-0.5 dark:bg-black/15">
                <ArrowUp size={15} weight="bold" />
              </span>
            </button>
          )}
        </div>

        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line px-2 pt-2.5 pb-1">
          <button type="button" onClick={() => setShowOpts((v) => !v)} aria-expanded={showOpts}
            className="inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-[12px] font-medium text-ink-3 hover:text-ink">
            <SlidersHorizontal size={14} /> {MODE_LABEL[options.mode]} search, {options.k} passages
          </button>
          <AnimatePresence initial={false}>
            {showOpts && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.35, ease: SPRING }} className="flex w-full flex-wrap items-center gap-x-5 gap-y-3 overflow-hidden px-1 pt-1 pb-1">
                <Segmented<Mode> label="Retrieval method" value={options.mode} options={["hybrid", "dense", "bm25"]}
                  labels={MODE_LABEL} onChange={(mode) => setOptions({ ...options, mode })} />
                <label className="inline-flex items-center gap-2 text-[13px] text-ink-2">
                  Passages
                  <select value={options.k} onChange={(e) => setOptions({ ...options, k: Number(e.target.value) })}
                    className="rounded-full bg-muted px-2.5 py-1 font-mono text-[13px] text-ink ring-1 ring-line">
                    {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                </label>
                <Toggle label="Compare with plain LLM" checked={options.compare_plain}
                  hint="Same model, same question, without your course material"
                  onChange={(v) => setOptions({ ...options, compare_plain: v })} />
                <Toggle label="Retrieval only" checked={options.retrieval_only}
                  hint="Show matching slides and pages without calling the model"
                  onChange={(v) => setOptions({ ...options, retrieval_only: v })} />
                <p className="w-full text-[12px] text-ink-3">{MODE_HELP[options.mode]}.</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </form>
    </div>
  );
}

/** Follow-up composer pinned to the bottom of the screen while reading an answer. */
function Dock({ options, setOptions, onAsk, onStop, busy }: AskProps) {
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-30 px-4 pb-5 md:pb-7">
      <div className="pointer-events-auto mx-auto max-w-[760px]">
        <Composer options={options} setOptions={setOptions} onAsk={onAsk} onStop={onStop} busy={busy} />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ One question + answer */

/** Reveal streamed text at a readable pace. The model can deliver a whole answer in a fraction
 *  of a second; easing the reveal keeps the streaming visible. Finished history shows instantly. */
function useReveal(target: string, animate: boolean) {
  const [shown, setShown] = useState(animate ? "" : target);
  const len = useRef(shown.length);
  useEffect(() => {
    if (!animate) { len.current = target.length; setShown(target); return; }
    let raf = 0;
    const step = () => {
      const remaining = target.length - len.current;
      if (remaining <= 0) return;  // caught up: stop until more text arrives
      len.current += Math.max(3, Math.ceil(remaining / 18));
      setShown(target.slice(0, len.current));
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, animate]);
  return shown;
}

export function TurnView({ turn, compact = false }: { turn: Turn; compact?: boolean }) {
  const reduce = useReducedMotion();
  // Animate only answers that started streaming while this view was open.
  const [live] = useState(() => !turn.done && !reduce);
  const answer = useReveal(turn.answer, live);
  const plain = useReveal(turn.plain, live);
  const revealing = live && (answer.length < turn.answer.length || plain.length < turn.plain.length);
  const [flash, setFlash] = useState<number | null>(null);
  const cite = (n: number) => {
    document.getElementById(`src-${turn.id}-${n}`)?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "nearest", inline: "center" });
    setFlash(n);
    window.setTimeout(() => setFlash(null), 1300);
  };
  const streaming = (!turn.done && !turn.error) || revealing;
  const skipped = turn.options.retrieval_only;

  return (
    <motion.article
      initial={reduce ? false : { opacity: 0, y: 16, filter: "blur(6px)" }}
      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      transition={{ duration: 0.7, ease: SPRING }}
      className={cx("grid gap-8", !compact && "xl:grid-cols-[minmax(0,1fr)_360px] xl:gap-10")}
    >
      <div className="min-w-0">
        {compact ? null : (
          <h1 className="text-[30px] leading-[1.08] font-semibold tracking-[-0.035em] text-ink md:text-[40px]">{turn.question}</h1>
        )}
        <div className={cx("flex flex-wrap items-center gap-2", !compact && "mt-5")}>
          <Badge icon={MagnifyingGlass}>{MODE_LABEL[turn.options.mode]} search</Badge>
          {turn.done && !skipped && !turn.error && (
            <Badge tone="accent" icon={Quotes}>{turn.cited.length} source{turn.cited.length === 1 ? "" : "s"} cited</Badge>
          )}
          {streaming && <span className="text-[12px] text-ink-3">{turn.hits ? "Writing the answer" : "Searching your material"}</span>}
        </div>

        <Card className="mt-5" coreClassName="p-6 md:p-8">
          <div className="mb-5 flex items-center gap-3">
            <IconTile icon={BookOpenText} accent />
            <span className="text-[13px] font-medium text-ink-3">{skipped ? "Retrieval only" : "Answer from your course material"}</span>
          </div>

          {turn.error && (
            <div className="mb-5 flex gap-2.5 rounded-[12px] bg-muted p-3.5 text-[14px] text-ink-2 ring-1 ring-line">
              <WarningCircle size={18} className="mt-0.5 shrink-0 text-ink" />
              <span>{turn.error} The retrieved passages are still listed.</span>
            </div>
          )}

          {skipped ? (
            <p className="text-[15px] text-ink-3">The model was not called. The matching passages are listed {compact ? "below" : "alongside"}.</p>
          ) : turn.answer ? (
            <div className={cx(turn.options.compare_plain && "grid gap-8 lg:grid-cols-2")}>
              <div>
                {turn.options.compare_plain && <p className="mb-3 text-[12px] font-semibold text-accent-text">BootUp, from your course material</p>}
                <Markdown text={answer} onCite={cite} />
                {streaming && !plain && <span className="caret" aria-hidden />}
              </div>
              {turn.options.compare_plain && (
                <div className="border-t border-line pt-6 lg:border-t-0 lg:border-l lg:pt-0 lg:pl-8">
                  <p className="mb-3 text-[12px] font-semibold text-ink-3">Plain LLM, same model, no course material</p>
                  {plain ? <Markdown text={plain} /> : <p className="text-[14px] text-ink-3">{streaming ? "Waiting for the first answer to finish" : "No plain answer."}</p>}
                  {streaming && plain && <span className="caret" aria-hidden />}
                </div>
              )}
            </div>
          ) : streaming ? (
            <div className="space-y-3" aria-label="Loading answer">
              <Skeleton className="h-4 w-[94%]" />
              <Skeleton className="h-4 w-[86%]" />
              <Skeleton className="h-4 w-[62%]" />
            </div>
          ) : null}
        </Card>
      </div>

      <aside className="min-w-0 xl:sticky xl:top-28 xl:self-start">
        <p className="mb-3 text-[13px] font-medium text-ink-3">
          Sources{turn.hits ? ` (${turn.hits.length})` : ""}
        </p>
        <div className={cx(
          "no-scrollbar -mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-2",
          !compact && "xl:mx-0 xl:flex-col xl:overflow-visible xl:px-0",
        )}>
          {turn.hits
            ? turn.hits.length
              ? turn.hits.map((h, i) => (
                <Rise key={h.id} index={i} className={cx("w-[300px] shrink-0 snap-start", !compact && "xl:w-auto")}>
                  <SourceCard hit={h} anchor={`src-${turn.id}-${h.n}`} cited={turn.cited.includes(h.n)} flash={flash === h.n} />
                </Rise>
              ))
              : <p className="text-[14px] text-ink-3">No passages matched this question.</p>
            : [0, 1, 2].map((i) => <Skeleton key={i} className="h-[150px] w-[300px] shrink-0 rounded-[22px] xl:w-auto" />)}
        </div>
      </aside>
    </motion.article>
  );
}
