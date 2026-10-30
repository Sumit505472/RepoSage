import {
  AlertCircle,
  MessageCircle,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

import CitationCard from "./CitationCard.jsx";
import LoadingIndicator from "./LoadingIndicator.jsx";

function ChatMessage({ message, repository }) {
  return (
    <article className="space-y-5">
      <div className="flex justify-end gap-3">
        <div className="max-w-[88%] rounded-2xl rounded-tr-md border border-cyan-300/10 bg-cyan-300/[0.07] px-4 py-3 sm:max-w-[78%]">
          <p className="whitespace-pre-wrap text-sm leading-6 text-slate-100">
            {message.question}
          </p>
        </div>
        <span className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.04] text-slate-400">
          <MessageCircle className="size-4" />
        </span>
      </div>

      {message.status === "loading" && <LoadingIndicator />}

      {message.status === "error" && (
        <div className="flex items-start gap-3">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-xl border border-rose-400/15 bg-rose-400/[0.06] text-rose-300">
            <AlertCircle className="size-4" />
          </span>
          <div className="rounded-2xl rounded-tl-md border border-rose-400/15 bg-rose-400/[0.04] px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-rose-200">
              Request failed
            </p>
            <p className="mt-1 text-sm leading-6 text-rose-100/80">
              {message.error}
            </p>
          </div>
        </div>
      )}

      {message.status === "complete" && (
        <div className="flex items-start gap-3">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-xl border border-cyan-300/15 bg-cyan-300/[0.07] text-cyan-200">
            <Sparkles className="size-4" />
          </span>
          <div className="min-w-0 flex-1 space-y-4">
            <div className="rounded-2xl rounded-tl-md border border-white/[0.07] bg-white/[0.025] px-4 py-3.5">
              {message.answer.insufficient_context && (
                <div className="mb-3 flex items-center gap-2 rounded-lg border border-amber-300/15 bg-amber-300/[0.05] px-3 py-2 text-[11px] font-medium text-amber-200">
                  <ShieldAlert className="size-3.5 shrink-0" />
                  The indexed context does not contain enough information to
                  answer this confidently.
                </div>
              )}
              <p className="whitespace-pre-wrap text-sm leading-7 text-slate-200">
                {message.answer.answer}
              </p>
            </div>

            {!message.answer.insufficient_context &&
              message.answer.citations.length > 0 && (
                <section aria-label="Source citations" className="space-y-2">
                  <h3 className="px-1 text-[10px] font-semibold uppercase tracking-[0.13em] text-slate-500">
                    Sources · {message.answer.citations.length}
                  </h3>
                  <div className="space-y-2">
                    {message.answer.citations.map((citation) => (
                      <CitationCard
                        key={citation.source_id}
                        citation={citation}
                        repository={repository}
                      />
                    ))}
                  </div>
                </section>
              )}
          </div>
        </div>
      )}
    </article>
  );
}

export default ChatMessage;
