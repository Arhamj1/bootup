import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ChartBar, ChatCircleText, Check, ClockCounterClockwise, Columns, Database, Desktop, FlowArrow, Moon, Sun,
  WarningCircle, IconContext,
} from "@phosphor-icons/react";
import { getStatus, setAccessCode, streamAsk, type AskOptions, type Status, type Turn } from "./api";
import { AskView } from "./AskView";
import { CompareView, DatasetView, EvalView, HistoryView, HowView } from "./Views";
import { Rise, SPRING, cx } from "./ui";

type View = "ask" | "history" | "compare" | "dataset" | "eval" | "how";
const NAV: { id: View; label: string; icon: React.ElementType }[] = [
  { id: "ask", label: "Ask", icon: ChatCircleText },
  { id: "history", label: "History", icon: ClockCounterClockwise },
  { id: "compare", label: "Compare", icon: Columns },
  { id: "dataset", label: "Dataset", icon: Database },
  { id: "eval", label: "Evaluation", icon: ChartBar },
  { id: "how", label: "How it works", icon: FlowArrow },
];
const HISTORY_KEY = "bootup.history.v1";
// v2: the default changed to dark, so earlier saved "system" values are ignored.
const THEME_KEY = "bootup.theme.v2";
const MAX_HISTORY = 60;
type ThemePref = "system" | "light" | "dark";

function loadHistory(): Turn[] {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]"); } catch { return []; }
}

function useTheme() {
  const [pref, setPref] = useState<ThemePref>(() => {
    try { return (localStorage.getItem(THEME_KEY) as ThemePref) || "dark"; } catch { return "dark"; }
  });
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => document.documentElement.classList.toggle("dark", pref === "dark" || (pref === "system" && mq.matches));
    apply();
    try { localStorage.setItem(THEME_KEY, pref); } catch { /* storage blocked */ }
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, [pref]);
  return { pref, setPref };
}

export default function App() {
  const [view, setView] = useState<View>("ask");
  const [status, setStatus] = useState<Status | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>(loadHistory);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [options, setOptions] = useState<AskOptions>({ mode: "hybrid", k: 4, compare_plain: false, retrieval_only: false });
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const theme = useTheme();

  // Poll while the server is still loading the model and index.
  const refreshStatus = useCallback(() => {
    let stop = false;
    const poll = () => getStatus().then((s) => {
      if (stop) return;
      setStatus(s); setStatusError(null); setOptions((o) => ({ ...o, k: s.default_k }));
      if (s.loading) window.setTimeout(poll, 1500);
    }).catch((e) => { if (!stop) { setStatusError(e.message); window.setTimeout(poll, 3000); } });
    poll();
    return () => { stop = true; };
  }, []);
  useEffect(refreshStatus, [refreshStatus]);

  // Persist finished turns only, newest first.
  useEffect(() => {
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(turns.filter((t) => t.done).slice(0, MAX_HISTORY))); } catch { /* full or blocked */ }
  }, [turns]);

  const update = (id: string, fn: (t: Turn) => Turn) => setTurns((ts) => ts.map((t) => (t.id === id ? fn(t) : t)));

  const ask = async (question: string) => {
    const id = crypto.randomUUID();
    const turn: Turn = { id, question, options, hits: null, answer: "", plain: "", cited: [], error: null, done: false, askedAt: Date.now() };
    setTurns((ts) => [turn, ...ts]);
    setCurrentId(id);
    setView("ask");
    window.scrollTo({ top: 0 });
    setBusy(true);
    const ctrl = new AbortController();
    abort.current = ctrl;
    try {
      await streamAsk(question, options, (e) => {
        if (e.event === "sources") update(id, (t) => ({ ...t, hits: e.data.hits }));
        else if (e.event === "token") update(id, (t) => ({ ...t, answer: t.answer + e.data.t }));
        else if (e.event === "plain") update(id, (t) => ({ ...t, plain: t.plain + e.data.t }));
        else if (e.event === "error") update(id, (t) => ({ ...t, error: e.data.message }));
        else if (e.event === "done") update(id, (t) => ({ ...t, cited: e.data.cited, done: true }));
      }, ctrl.signal);
    } catch (err) {
      const stopped = (err as Error).name === "AbortError";
      update(id, (t) => ({ ...t, done: true, error: stopped ? (t.error ?? "Stopped.") : (err as Error).message }));
    } finally {
      update(id, (t) => ({ ...t, done: true }));
      setBusy(false);
      abort.current = null;
    }
  };

  if (status?.auth_required && !status.authorized) {
    return (
      <IconContext.Provider value={{ size: 18, weight: "light" }}>
        <Gate course={status.course} onUnlocked={refreshStatus} />
      </IconContext.Provider>
    );
  }

  const go = (v: View) => {
    if (v === "ask" && view === "ask") setCurrentId(null);  // second click on Ask returns to the start page
    setView(v);
    window.scrollTo({ top: 0 });
  };
  const current = turns.find((t) => t.id === currentId) ?? null;

  return (
    <IconContext.Provider value={{ size: 18, weight: "light" }}>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-full focus:bg-core focus:px-4 focus:py-2">
        Skip to content
      </a>
      <header className="sticky top-0 z-30 px-3 pt-3 md:pt-5">
        <div className="glass mx-auto flex w-full max-w-[1080px] items-center gap-2 rounded-full p-1.5 md:w-max">
          <button type="button" onClick={() => go("ask")} className="flex shrink-0 items-center gap-2.5 rounded-full py-1 pr-3 pl-1">
            <span className="grid h-8 w-8 place-items-center rounded-full bg-accent text-[15px] font-bold tracking-tight text-accent-ink">B</span>
            <span className="hidden text-[15px] font-semibold tracking-tight text-ink sm:inline">BootUp</span>
          </button>
          <nav aria-label="Sections" className="no-scrollbar flex min-w-0 flex-1 gap-0.5 overflow-x-auto">
            {NAV.map(({ id, label, icon: Icon }) => (
              <button key={id} type="button" onClick={() => go(id)} aria-current={view === id ? "page" : undefined}
                className={cx(
                  "relative flex shrink-0 items-center gap-2 rounded-full px-3.5 py-2 text-[13px] font-medium whitespace-nowrap transition-colors duration-300",
                  view === id ? "text-ink" : "text-ink-3 hover:text-ink",
                )}>
                {view === id && (
                  <motion.span layoutId="nav-pill" className="absolute inset-0 rounded-full bg-core shadow-float ring-1 ring-line"
                    transition={{ duration: 0.5, ease: SPRING }} />
                )}
                <Icon size={16} weight={view === id ? "fill" : "light"} className={cx("relative", view === id && "text-accent-text")} />
                <span className="relative">{label}</span>
                {id === "history" && turns.length > 0 && <span className="relative font-mono text-[11px] text-ink-3">{turns.length}</span>}
              </button>
            ))}
          </nav>
          <StatusMenu status={status} error={statusError} theme={theme} />
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-[1180px] px-4 pt-10 pb-24 md:px-8 md:pt-16">
        {status?.index_error && view === "ask" && (
          <div className="mb-8 flex gap-2.5 rounded-[22px] bg-muted p-4 text-[14px] text-ink-2 ring-1 ring-line">
            <WarningCircle size={18} className="mt-0.5 shrink-0" /> No index loaded. Open Dataset and use Rebuild index.
          </div>
        )}
        <AnimatePresence mode="wait">
          <motion.div key={view} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}>
            {view === "ask" && (
              <AskView status={status} turn={current} options={options} setOptions={setOptions}
                onAsk={ask} onStop={() => abort.current?.abort()} onHome={() => setCurrentId(null)} busy={busy} />
            )}
            {view === "history" && (
              <HistoryView turns={turns.filter((t) => t.done)} onClear={() => { setTurns([]); setCurrentId(null); }}
                onOpen={(id) => { setCurrentId(id); go("ask"); setView("ask"); }} />
            )}
            {view === "compare" && <CompareView />}
            {view === "dataset" && <DatasetView onRebuilt={refreshStatus} canRebuild={!status?.public} />}
            {view === "eval" && <EvalView />}
            {view === "how" && <HowView status={status} />}
          </motion.div>
        </AnimatePresence>
      </main>
    </IconContext.Provider>
  );
}

/** Status light + popover with the real backend state and the theme choice. */
function StatusMenu({ status, error, theme }: {
  status: Status | null; error: string | null; theme: { pref: ThemePref; setPref: (p: ThemePref) => void };
}) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);
  const state = error ? "error" : !status || status.loading ? "loading" : status.key_set ? "ready" : "nokey";
  const label = { error: "API not reachable", loading: "Loading", ready: "Ready", nokey: "No Groq key" }[state];
  return (
    <div ref={box} className="relative shrink-0">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-label={`Status: ${label}`}
        className="flex items-center gap-2 rounded-full bg-muted px-3 py-2 text-[12px] font-medium text-ink-2 ring-1 ring-line hover:text-ink">
        {/* The dot shows real backend state: ready, loading or a problem. */}
        <span className={cx("h-2 w-2 rounded-full", state === "ready" ? "bg-accent" : state === "loading" ? "animate-pulse bg-ink-3 motion-reduce:animate-none" : "bg-ink")} />
        <span className="hidden md:inline">{label}</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: -6, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.3, ease: SPRING }}
            className="glass absolute top-[calc(100%+10px)] right-0 w-[280px] rounded-[22px] p-4 text-[13px]">
            {error ? (
              <p className="text-ink-2">The API did not answer: {error}</p>
            ) : status ? (
              <dl className="grid gap-2">
                <div className="flex items-center gap-1.5 font-medium">
                  {status.key_set
                    ? <><Check size={14} weight="bold" className="text-accent-text" /><span className="text-ink">Groq key found</span></>
                    : <><WarningCircle size={14} /><span className="text-ink-2">Groq key not set (retrieval still works)</span></>}
                </div>
                <Row k="Model" v={status.llm_model} />
                <Row k="Embedder" v={status.embedder.split("/").pop() ?? ""} />
                <Row k="Chunks" v={status.loading ? "loading" : status.chunks ?? "none"} />
                {status.course_files != null && <Row k="Course files" v={status.course_files} />}
              </dl>
            ) : <p className="text-ink-3">Connecting</p>}
            <div className="mt-4 border-t border-line pt-3">
              <p className="mb-2 text-[12px] text-ink-3">Appearance</p>
              <div role="radiogroup" aria-label="Appearance" className="grid grid-cols-3 gap-1 rounded-full bg-muted p-1 ring-1 ring-line">
                {([["system", "Auto", Desktop], ["light", "Light", Sun], ["dark", "Dark", Moon]] as const).map(([v, l, I]) => (
                  <button key={v} type="button" role="radio" aria-checked={theme.pref === v} onClick={() => theme.setPref(v)}
                    className={cx("flex items-center justify-center gap-1 rounded-full py-1.5 text-[12px] font-medium transition-colors",
                      theme.pref === v ? "bg-core text-ink shadow-float ring-1 ring-line" : "text-ink-3 hover:text-ink")}>
                    <I size={13} /> {l}
                  </button>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Shown on the public site until the visitor enters the access code. */
function Gate({ course, onUnlocked }: { course: string; onUnlocked: () => void }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    setChecking(true); setError(null);
    setAccessCode(code.trim());
    try {
      const s = await getStatus();
      if (s.authorized) onUnlocked();
      else setError("That code is not right. Check it with the person who shared this link.");
    } catch (err) {
      setError((err as Error).message);
    }
    setChecking(false);
  };
  return (
    <main className="grid min-h-[100dvh] place-items-center px-4">
      <Rise className="w-full max-w-[420px]">
        <div className="shell">
          <form onSubmit={submit} className="core p-7">
            <span className="grid h-11 w-11 place-items-center rounded-full bg-accent text-[18px] font-bold text-accent-ink">B</span>
            <h1 className="mt-5 text-[26px] leading-tight font-semibold tracking-[-0.03em] text-ink">BootUp</h1>
            <p className="mt-1 text-[14px] text-ink-3">{course} study assistant. Enter the access code you were given.</p>
            <label htmlFor="code" className="mt-6 block text-[13px] font-medium text-ink-2">Access code</label>
            <input id="code" type="password" autoComplete="off" autoFocus value={code} onChange={(e) => setCode(e.target.value)}
              aria-invalid={!!error} aria-describedby={error ? "code-error" : undefined}
              className="mt-2 w-full rounded-full bg-muted px-4 py-3 text-[15px] text-ink ring-1 ring-line outline-none focus:ring-accent" />
            {error && <p id="code-error" className="mt-2 text-[13px] text-ink-2">{error}</p>}
            <button type="submit" disabled={!code.trim() || checking}
              className="mt-5 w-full rounded-full bg-accent py-3 text-[15px] font-medium text-accent-ink transition-transform duration-300 ease-spring active:scale-[0.98] disabled:opacity-40">
              {checking ? "Checking" : "Continue"}
            </button>
          </form>
        </div>
      </Rise>
    </main>
  );
}

function Row({ k, v }: { k: string; v: string | number }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-ink-3">{k}</dt>
      <dd className="truncate font-mono text-ink-2" title={String(v)}>{v}</dd>
    </div>
  );
}
