import { ArrowRight, LoaderCircle, Link2 } from "lucide-react";

function RepositoryInput({
  value,
  onChange,
  onSubmit,
  isLoading,
  disabled,
}) {
  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <label
        htmlFor="repository-url"
        className="block text-xs font-medium text-slate-300"
      >
        GitHub repository URL
      </label>
      <div className="relative">
        <Link2 className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
        <input
          id="repository-url"
          type="url"
          autoComplete="url"
          required
          maxLength={2048}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="https://github.com/owner/repo"
          disabled={isLoading || disabled}
          className="h-11 w-full rounded-xl border border-white/[0.09] bg-[#080b12] pl-10 pr-3 text-xs text-slate-100 outline-none transition placeholder:text-slate-600 hover:border-white/[0.15] focus:border-cyan-300/50 focus:ring-2 focus:ring-cyan-300/10 disabled:opacity-60"
        />
      </div>
      <button
        type="submit"
        disabled={isLoading || disabled || !value.trim()}
        className="flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-cyan-300 px-4 text-xs font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
      >
        {isLoading ? (
          <>
            <LoaderCircle className="size-4 animate-spin" />
            Indexing repository…
          </>
        ) : (
          <>
            Index repository
            <ArrowRight className="size-4" />
          </>
        )}
      </button>
      <p className="text-[11px] leading-5 text-slate-600">
        Public repositories only. Indexing may take a moment for larger projects.
      </p>
    </form>
  );
}

export default RepositoryInput;
