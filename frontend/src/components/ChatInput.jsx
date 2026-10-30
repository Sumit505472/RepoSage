import { ArrowUp, LoaderCircle, LockKeyhole } from "lucide-react";

function ChatInput({ value, onChange, onSubmit, disabled, isLoading }) {
  const isDisabled = disabled || isLoading || !value.trim();

  return (
    <form
      onSubmit={onSubmit}
      className={`rounded-2xl border bg-[#0d121b] p-2 transition ${
        disabled
          ? "border-white/[0.06] opacity-80"
          : "border-white/[0.1] focus-within:border-cyan-300/30 focus-within:shadow-[0_0_30px_-18px_rgba(34,211,238,0.3)]"
      }`}
    >
      <label htmlFor="repository-question" className="sr-only">
        Ask a question about the repository
      </label>
      <textarea
        id="repository-question"
        rows={2}
        maxLength={2000}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            event.currentTarget.form?.requestSubmit();
          }
        }}
        placeholder={
          disabled
            ? "Index a repository before asking a question…"
            : "Ask anything about this codebase…"
        }
        disabled={disabled || isLoading}
        className="max-h-40 min-h-14 w-full resize-y bg-transparent px-3 py-2 text-sm leading-6 text-slate-100 outline-none placeholder:text-slate-600 disabled:cursor-not-allowed"
      />
      <div className="flex items-center justify-between border-t border-white/[0.06] px-2 pt-2">
        <span className="flex items-center gap-1.5 text-[10px] text-slate-600">
          <LockKeyhole className="size-3" />
          Grounded in retrieved code
        </span>
        <div className="flex items-center gap-3">
          <span className="hidden text-[10px] text-slate-600 sm:inline">
            Ctrl + Enter to send
          </span>
          <button
            type="submit"
            disabled={isDisabled}
            aria-label={isLoading ? "Generating answer" : "Send question"}
            className="flex size-9 items-center justify-center rounded-xl bg-cyan-300 text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500"
          >
            {isLoading ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : (
              <ArrowUp className="size-4" />
            )}
          </button>
        </div>
      </div>
    </form>
  );
}

export default ChatInput;
