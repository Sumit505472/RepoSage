import { Sparkles } from "lucide-react";

function LoadingIndicator() {
  return (
    <div className="flex items-start gap-3" role="status" aria-live="polite">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-xl border border-cyan-300/15 bg-cyan-300/[0.07] text-cyan-200">
        <Sparkles className="size-4" />
      </span>
      <div className="rounded-2xl rounded-tl-md border border-white/[0.07] bg-white/[0.025] px-4 py-3">
        <p className="text-xs text-slate-400">Reading the repository context</p>
        <span className="mt-2 flex gap-1" aria-hidden="true">
          <span className="size-1.5 animate-bounce rounded-full bg-cyan-300 [animation-delay:-0.3s]" />
          <span className="size-1.5 animate-bounce rounded-full bg-cyan-300 [animation-delay:-0.15s]" />
          <span className="size-1.5 animate-bounce rounded-full bg-cyan-300" />
        </span>
      </div>
    </div>
  );
}

export default LoadingIndicator;
