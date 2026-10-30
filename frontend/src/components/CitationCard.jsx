import { ExternalLink, FileCode2 } from "lucide-react";

import { citationUrl } from "../utils/github.js";

function CitationCard({ citation, repository }) {
  const sourceUrl = citationUrl(repository, citation);

  return (
    <article className="overflow-hidden rounded-xl border border-white/[0.08] bg-[#0b1018]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.06] px-3.5 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <FileCode2 className="size-4 shrink-0 text-cyan-200" />
          <span className="truncate font-mono text-[11px] text-slate-200">
            {citation.file_path}
          </span>
          <span className="shrink-0 rounded-md bg-white/[0.05] px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
            L{citation.start_line}–L{citation.end_line}
          </span>
        </div>
        {sourceUrl && (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex shrink-0 items-center gap-1 text-[10px] font-medium text-cyan-200 transition hover:text-cyan-100"
          >
            View source
            <ExternalLink className="size-3" />
          </a>
        )}
      </div>
      {citation.relevant_content && (
        <pre className="max-h-36 overflow-auto whitespace-pre-wrap break-words px-3.5 py-3 font-mono text-[10px] leading-5 text-slate-400">
          {citation.relevant_content.trim()}
        </pre>
      )}
    </article>
  );
}

export default CitationCard;
