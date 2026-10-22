import { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { FileText } from "@phosphor-icons/react";
import type { Hit } from "./api";
import { cx } from "./ui";

/** Model output -> markdown the renderer understands:
 *  \( x \) and \[ x \] become $x$ / $$x$$, and citations [1] or [1, 2] become links we can click. */
export function prepare(text: string) {
  return text
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => `$$${m}$$`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, m) => `$${m}$`)
    .replace(/\[(\d+(?:\s*,\s*\d+)+)\]/g, (_, list: string) => list.split(/\s*,\s*/).map((n) => `[${n}]`).join(""))
    .replace(/\[(\d+)\](?!\()/g, (_, n) => `[\\[${n}\\]](#cite-${n})`);
}

export const Markdown = memo(function Markdown({ text, onCite }: { text: string; onCite?: (n: number) => void }) {
  return (
    <div className="answer">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          a: ({ href, children }) => {
            const m = href?.match(/^#cite-(\d+)$/);
            if (m && onCite) {
              return (
                <button
                  type="button"
                  onClick={() => onCite(Number(m[1]))}
                  className="mx-0.5 inline-flex h-[20px] min-w-[20px] -translate-y-[1px] items-center justify-center rounded-[6px] bg-accent-soft px-1 align-middle font-mono text-[11px] font-semibold text-accent-text hover:bg-accent hover:text-accent-ink"
                  aria-label={`Show source ${m[1]}`}
                >
                  {m[1]}
                </button>
              );
            }
            return <a href={href} target="_blank" rel="noreferrer" className="text-accent-text underline underline-offset-2">{children}</a>;
          },
        }}
      >
        {prepare(text)}
      </ReactMarkdown>
    </div>
  );
});

export function SourceCard({ hit, cited, flash, anchor }: { hit: Hit; cited: boolean; flash: boolean; anchor: string }) {
  const ranks = Object.entries(hit.ranks).map(([m, r]) => `${m === "bm25" ? "BM25" : "dense"} #${r}`).join(", ");
  return (
    <div
      id={anchor}
      className={cx("shell h-full scroll-mt-28 !p-1 transition-shadow duration-500 ease-spring", flash && "flash")}
    >
      <div className={cx("core h-full p-4", cited && "!shadow-[inset_0_0_0_1px_var(--accent)]")}>
        <header className="flex items-start gap-3">
          <span
            className={cx(
              "grid h-7 w-7 shrink-0 place-items-center rounded-[10px] font-mono text-[12px] font-semibold",
              cited ? "bg-accent text-accent-ink" : "bg-muted text-ink-2 ring-1 ring-line",
            )}
          >
            {hit.n}
          </span>
          <div className="min-w-0 flex-1">
            <p className="flex items-center gap-1.5 text-[13px] font-medium text-ink" title={hit.file}>
              <FileText size={14} weight="light" className="shrink-0 text-ink-3" />
              <span className="truncate font-mono">{hit.name}</span>
            </p>
            <p className="mt-0.5 text-[12px] text-ink-3">
              {hit.locator} | {hit.topic}
            </p>
          </div>
          {cited && <span className="shrink-0 rounded-[8px] bg-accent-soft px-2 py-0.5 text-[11px] font-semibold text-accent-text">cited</span>}
        </header>
        <p className="mt-3 line-clamp-4 text-[13px] leading-relaxed text-ink-2">{hit.text}</p>
        {ranks && <p className="mt-3 font-mono text-[11px] text-ink-3">{hit.source_type} | rank {ranks}</p>}
      </div>
    </div>
  );
}
