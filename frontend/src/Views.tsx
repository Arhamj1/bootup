import { useEffect, useState } from "react";
import {
  ArrowClockwise, CaretRight, ChartBar, ClockCounterClockwise, Columns, Database, FileText,
  MagnifyingGlass, Trash, WarningCircle,
} from "@phosphor-icons/react";
import {
  MODE_LABEL, getChunks, getCompare, getEvalRun, getEvalRuns, getFiles, getStats, rebuildIndex,
  type Hit, type Mode, type Status, type Turn,
} from "./api";
import { TurnView } from "./AskView";
import { Badge, Card, Empty, PageTitle, Skeleton, cx } from "./ui";

/* ------------------------------------------------------------------ History */
export function HistoryView({ turns, onOpen, onClear }: {
  turns: Turn[]; onOpen: (id: string) => void; onClear: () => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  if (!turns.length) {
    return (
      <>
        <PageTitle title="History" />
        <Empty icon={ClockCounterClockwise} title="No questions yet">
          Questions you ask are saved here in this browser, newest first.
        </Empty>
      </>
    );
  }
  const fmt = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  return (
    <>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <PageTitle title="History" sub={`${turns.length} question${turns.length === 1 ? "" : "s"}, saved in this browser.`} />
        <button type="button" onClick={() => { if (confirm("Clear all saved questions?")) onClear(); }}
          className="mb-6 inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-2 text-[13px] text-ink-2 hover:text-ink">
          <Trash size={15} /> Clear history
        </button>
      </div>
      <ul className="flex flex-col gap-2">
        {turns.map((t) => (
          <li key={t.id}>
            <Card coreClassName="overflow-hidden">
              <button type="button" onClick={() => setOpen(open === t.id ? null : t.id)}
                className="flex w-full items-center gap-3 px-4 py-3.5 text-left hover:bg-muted">
                <CaretRight size={14} className={cx("shrink-0 text-ink-3 transition-transform", open === t.id && "rotate-90")} />
                <span className="flex-1 text-[15px] font-medium text-ink">{t.question}</span>
                <span className="hidden shrink-0 text-[12px] text-ink-3 sm:inline">{fmt.format(t.askedAt)}</span>
                {t.done && !t.error && !t.options.retrieval_only && <Badge tone="accent">{t.cited.length} cited</Badge>}
              </button>
              {open === t.id && (
                <div className="border-t border-line p-4 md:p-5">
                  <TurnView turn={t} compact />
                  <button type="button" onClick={() => onOpen(t.id)} className="mt-4 text-[13px] font-medium text-accent-text hover:underline">
                    Open in Ask
                  </button>
                </div>
              )}
            </Card>
          </li>
        ))}
      </ul>
    </>
  );
}

/* ------------------------------------------------------------------ Compare */
export function CompareView() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<{ question: string; results: Record<Mode, Hit[]>; shared: string[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = async () => {
    if (!q.trim()) return;
    setLoading(true); setError(null);
    try { setRes(await getCompare(q.trim())); } catch (e) { setError((e as Error).message); }
    setLoading(false);
  };
  return (
    <>
      <PageTitle title="Compare retrieval"
        sub="One question searched three ways, top 5 each. Keyword-heavy questions (a function name, a flag, an error code) are where the methods tend to differ." />
      <form onSubmit={(e) => { e.preventDefault(); run(); }} className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="cmpq" className="sr-only">Question</label>
        <input id="cmpq" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Bakery algorithm ticket number"
          className="flex-1 rounded-full border border-line bg-core px-3.5 py-2.5 text-[15px] text-ink outline-none placeholder:text-ink-3 focus:border-accent" />
        <button type="submit" disabled={!q.trim() || loading}
          className="inline-flex items-center justify-center gap-2 rounded-full bg-accent px-4 py-2.5 text-[14px] font-medium text-accent-ink active:scale-[0.98] disabled:opacity-40">
          <MagnifyingGlass size={16} weight="bold" /> Compare
        </button>
      </form>
      {error && <p className="mt-4 text-[14px] text-ink-2">{error}</p>}
      {loading && <div className="mt-6 grid gap-4 lg:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-72 rounded-[28px]" />)}</div>}
      {res && !loading && (
        <>
          <p className="mt-6 text-[13px] text-ink-3">
            {res.shared.length} passage{res.shared.length === 1 ? "" : "s"} appear in both the dense and the BM25 top 5.
          </p>
          <div className="mt-3 grid gap-4 lg:grid-cols-3">
            {(["dense", "bm25", "hybrid"] as Mode[]).map((m) => (
              <Card key={m} coreClassName="p-5">
                <h2 className="mb-3 text-[15px] font-semibold text-ink">{MODE_LABEL[m]}</h2>
                {res.results[m].length === 0 && <p className="text-[13px] text-ink-3">No matches.</p>}
                <ol className="flex flex-col gap-3">
                  {res.results[m].map((h) => {
                    const both = res.shared.includes(h.id);
                    return (
                      <li key={h.id} className="flex gap-2.5">
                        <span className="mt-0.5 font-mono text-[12px] text-ink-3">{h.n}</span>
                        <div className="min-w-0">
                          <p className="flex flex-wrap items-center gap-1.5 text-[13px]" title={h.file}>
                            <span className="truncate font-mono text-ink">{h.name}</span>
                            <span className="text-ink-3">{h.locator}</span>
                            {both && <Badge tone="accent">both</Badge>}
                          </p>
                          <p className="mt-1 line-clamp-3 text-[12px] leading-relaxed text-ink-3">{h.text}</p>
                        </div>
                      </li>
                    );
                  })}
                </ol>
              </Card>
            ))}
          </div>
        </>
      )}
      {!res && !loading && !error && (
        <div className="mt-6"><Empty icon={Columns} title="Try a keyword-heavy question">For example "Bakery algorithm ticket number" or "SSTF starvation".</Empty></div>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ Dataset */
export function DatasetView({ onRebuilt, canRebuild = true }: { onRebuilt: () => void; canRebuild?: boolean }) {
  const [stats, setStats] = useState<Record<string, any> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [files, setFiles] = useState<{ file: string; name: string; chunks: number }[]>([]);
  const [file, setFile] = useState("");
  const [chunks, setChunks] = useState<{ locator: string; words: number; text: string }[] | null>(null);
  const [building, setBuilding] = useState(false);
  const [buildMsg, setBuildMsg] = useState<string | null>(null);

  const load = () => {
    getStats().then(setStats).catch((e) => setErr(e.message));
    getFiles().then((f) => { setFiles(f); if (f.length && !file) setFile(f.find((x) => x.file.startsWith("course/"))?.file ?? f[0].file); }).catch(() => setFiles([]));
  };
  useEffect(load, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (file) { setChunks(null); getChunks(file).then(setChunks).catch(() => setChunks([])); } }, [file]);

  const rebuild = async () => {
    setBuilding(true); setBuildMsg(null);
    try {
      const r = await rebuildIndex();
      setBuildMsg(`Indexed ${r.chunks_indexed} chunks from ${r.files_used} files.`);
      load(); onRebuilt();
    } catch (e) { setBuildMsg((e as Error).message); }
    setBuilding(false);
  };

  const topics = stats ? Object.entries(stats.chunks_by_topic as Record<string, number>).sort((a, b) => b[1] - a[1]) : [];
  const maxTopic = Math.max(1, ...topics.map(([, n]) => n));
  return (
    <>
      <PageTitle title="Dataset" sub="Counts from the last index build." />
      {err && !stats && <Empty icon={Database} title="No statistics yet">{err}{canRebuild && " Use Rebuild index below."}</Empty>}
      {stats && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {[
              ["Files used", stats.files_used],
              ["Chunks indexed", stats.chunks_indexed],
              ["Near-duplicates dropped", stats.duplicates_dropped],
              ["Mean words per chunk", stats.words_per_chunk?.mean],
            ].map(([label, value]) => (
              <Card key={label} coreClassName="p-5">
                <p className="text-[12px] text-ink-3">{label}</p>
                <p className="mt-1 font-mono text-[26px] font-semibold tracking-tight text-ink">{value ?? "-"}</p>
              </Card>
            ))}
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-[3fr_2fr]">
            <Card coreClassName="p-6">
              <h2 className="text-[15px] font-semibold text-ink">Chunks by topic</h2>
              <ul className="mt-4 flex flex-col gap-2.5">
                {topics.map(([t, n]) => (
                  <li key={t} className="grid grid-cols-[120px_1fr_44px] items-center gap-3 text-[13px]">
                    <span className="truncate text-ink-2">{t}</span>
                    <span className="h-2 rounded-full bg-accent/80" style={{ width: `${(n / maxTopic) * 100}%` }} />
                    <span className="text-right font-mono text-ink-3">{n}</span>
                  </li>
                ))}
              </ul>
            </Card>
            <Card coreClassName="p-6">
              <h2 className="text-[15px] font-semibold text-ink">By source type</h2>
              <ul className="mt-4 flex flex-col gap-2 text-[14px]">
                {Object.entries(stats.chunks_by_source_type as Record<string, number>).map(([t, n]) => (
                  <li key={t} className="flex justify-between"><span className="text-ink-2">{t}</span><span className="font-mono text-ink">{n} chunks</span></li>
                ))}
                {Object.entries((stats.files_by_source_type ?? {}) as Record<string, number>).map(([t, n]) => (
                  <li key={`f-${t}`} className="flex justify-between"><span className="text-ink-2">{t} files</span><span className="font-mono text-ink">{n}</span></li>
                ))}
              </ul>
              <p className="mt-4 text-[12px] text-ink-3">Built {stats.built_at ?? ""} with {stats.embedder ?? ""}.</p>
              {stats.files_skipped?.length > 0 && (
                <div className="mt-3 rounded-[12px] bg-muted p-3 text-[12px] text-ink-2">
                  <p className="mb-1 flex items-center gap-1 font-semibold"><WarningCircle size={14} /> Skipped files</p>
                  {stats.files_skipped.map((s: { file: string; reason: string }) => <p key={s.file}>{s.file}: {s.reason}</p>)}
                </div>
              )}
            </Card>
          </div>
        </>
      )}

      {files.length > 0 && (
        <Card className="mt-4" coreClassName="p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-[15px] font-semibold text-ink">Browse chunks</h2>
            <label className="flex items-center gap-2 text-[13px] text-ink-2">
              <span className="sr-only">File</span>
              <FileText size={15} />
              <select value={file} onChange={(e) => setFile(e.target.value)}
                className="max-w-[340px] rounded-full border border-line bg-core px-2.5 py-1.5 font-mono text-[12px] text-ink">
                {files.map((f) => <option key={f.file} value={f.file}>{f.file.split("/").slice(0, -1).join("/")}/{f.name} ({f.chunks})</option>)}
              </select>
            </label>
          </div>
          <div className="mt-4 grid max-h-[460px] gap-2 overflow-y-auto pr-1">
            {chunks === null ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-16" />) : chunks.map((c, i) => (
              <details key={i} className="rounded-[12px] border border-line px-3.5 py-2.5">
                <summary className="cursor-pointer text-[13px] text-ink-2"><span className="font-mono text-ink">{c.locator}</span> | {c.words} words</summary>
                <p className="mt-2 whitespace-pre-wrap text-[13px] leading-relaxed text-ink-2">{c.text}</p>
              </details>
            ))}
          </div>
        </Card>
      )}

      {canRebuild && <Card className="mt-4" coreClassName="flex flex-wrap items-center justify-between gap-3 p-6">
        <div>
          <h2 className="text-[15px] font-semibold text-ink">Rebuild index</h2>
          <p className="mt-0.5 text-[13px] text-ink-3">Run this after adding or removing files in data/raw.</p>
          {buildMsg && <p className="mt-2 text-[13px] text-ink-2">{buildMsg}</p>}
        </div>
        <button type="button" onClick={rebuild} disabled={building}
          className="inline-flex items-center gap-2 rounded-full border border-line bg-core px-4 py-2 text-[14px] font-medium text-ink hover:border-accent active:scale-[0.98] disabled:opacity-50">
          <ArrowClockwise size={16} className={cx(building && "animate-spin motion-reduce:animate-none")} />
          {building ? "Rebuilding" : "Rebuild index"}
        </button>
      </Card>}
    </>
  );
}

/* --------------------------------------------------------------- Evaluation */
export function EvalView() {
  const [runs, setRuns] = useState<string[] | null>(null);
  const [pick, setPick] = useState("");
  const [res, setRes] = useState<Record<string, any> | null>(null);
  useEffect(() => { getEvalRuns().then((r) => { setRuns(r.runs); if (r.runs[0]) setPick(r.runs[0]); }).catch(() => setRuns([])); }, []);
  useEffect(() => { if (pick) getEvalRun(pick).then(setRes).catch(() => setRes(null)); }, [pick]);

  if (runs === null) return <Skeleton className="h-40 rounded-[28px]" />;
  if (!runs.length) {
    return (
      <>
        <PageTitle title="Evaluation" />
        <Empty icon={ChartBar} title="No evaluation has been run yet">
          Write 15 to 20 labelled questions in eval/questions.json (template: eval/questions.template.json), then run
          <code className="mx-1 rounded-[6px] bg-muted px-1.5 py-0.5 font-mono text-[12px] text-ink">python -m bootup.evaluate</code>.
          Results appear here. Until then there are no numbers to report.
        </Empty>
      </>
    );
  }
  const meta = res?.meta ?? {};
  const n = res?.n_questions_used;
  return (
    <>
      <PageTitle title="Evaluation" sub="Results of python -m bootup.evaluate on your labelled questions." />
      <select value={pick} onChange={(e) => setPick(e.target.value)} className="rounded-full border border-line bg-core px-3 py-2 font-mono text-[13px] text-ink">
        {runs.map((r) => <option key={r}>{r}</option>)}
      </select>
      {res && (
        <div className="mt-4 flex flex-col gap-4">
          {!meta.reportable && (
            <div className="flex gap-2 rounded-[12px] border border-line bg-muted p-3 text-[14px] text-ink-2">
              <WarningCircle size={18} className="mt-0.5 shrink-0" /> This run used the offline stand-in embedder. Its numbers are NOT reportable.
            </div>
          )}
          <p className="text-[13px] text-ink-3">Run at {meta.run_at ?? "?"} | embedder {meta.embedder ?? "?"} | {n} questions</p>
          <Card coreClassName="overflow-x-auto p-2">
            <table className="w-full text-[14px]">
              <thead><tr className="text-left text-[12px] text-ink-3">{["Method", "hit@3", "hit@5", "MRR@10"].map((h) => <th key={h} className="px-4 py-2.5 font-medium">{h}</th>)}</tr></thead>
              <tbody>
                {Object.entries(res.summary as Record<string, any>).map(([m, s]) => (
                  <tr key={m} className="border-t border-line">
                    <td className="px-4 py-2.5 text-ink">{MODE_LABEL[m as Mode] ?? m}</td>
                    <td className="px-4 py-2.5 font-mono">{s["hit@3"]}/{s.n}</td>
                    <td className="px-4 py-2.5 font-mono">{s["hit@5"]}/{s.n}</td>
                    <td className="px-4 py-2.5 font-mono">{Number(s["mrr@10"]).toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <p className="text-[13px] text-ink-3">With {n} questions, a difference of one or two questions between methods is not strong evidence either way.</p>
        </div>
      )}
    </>
  );
}

/* ------------------------------------------------------------- How it works */
export function HowView({ status }: { status: Status | null }) {
  const s = status?.settings;
  const offline = [
    ["Read", "Your slides, notes and textbook chapters (PDF, PowerPoint, Word, text) from data/raw/."],
    ["Clean", "Drop page numbers and repeated headers, join hyphenated line breaks, restore spaces in slide PDFs."],
    ["Split", `Slides per slide, running text into chunks of about ${s?.chunk_tokens ?? "?"} tokens with ${s?.overlap_pct ?? "?"}% overlap.`],
    ["Tag", "Every chunk keeps its file, source type, topic and page or slide."],
    ["Index", `Embed with ${status?.embedder ?? "the embedding model"}, drop near-duplicates, store in ChromaDB, and build a BM25 index over the same chunks.`],
  ];
  const online = [
    ["Rewrite", "Turn the question into textbook keywords, so everyday wording still finds the right section."],
    ["Search", `Take the top ${s?.top_k_each ?? "?"} chunks from dense search and from BM25, using the question plus those keywords.`],
    ["Fuse", `Merge the two rankings with Reciprocal Rank Fusion: score = sum of 1 / (${s?.rrf_k ?? "?"} + rank).`],
    ["Answer", `Send the best ${s?.top_k_final ?? "?"} passages to ${status?.llm_model ?? "the model"} as the main source, cited as [1], [2]. Anything they do not cover is marked "(general knowledge)".`],
    ["Show", "Stream the answer as it is written, with its sources and their rank in each method."],
  ];
  const Block = ({ title, rows }: { title: string; rows: string[][] }) => (
    <Card coreClassName="p-6 md:p-8">
      <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
      <ol className="mt-4 flex flex-col gap-4">
        {rows.map(([verb, text]) => (
          <li key={verb} className="grid grid-cols-[72px_1fr] gap-3">
            <span className="text-[13px] font-semibold text-accent-text">{verb}</span>
            <span className="text-[14px] leading-relaxed text-ink-2">{text}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
  return (
    <>
      <PageTitle title="How it works" sub="Search your material two ways, merge the results, and answer from what was found." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Block title="When the index is built" rows={offline} />
        <Block title="When you ask a question" rows={online} />
      </div>
    </>
  );
}
