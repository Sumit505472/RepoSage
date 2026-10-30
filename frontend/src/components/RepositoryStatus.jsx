import {
  AlertCircle,
  CheckCircle2,
  GitBranch,
  LoaderCircle,
  PackageOpen,
} from "lucide-react";

function RepositoryStatus({ repository, isLoading, error }) {
  return (
    <section
      aria-live="polite"
      className="mt-5 rounded-2xl border border-white/[0.07] bg-[#080b12] p-4"
    >
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
          Index status
        </span>
        {repository && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/15 bg-emerald-400/[0.06] px-2 py-1 text-[10px] font-medium text-emerald-300">
            <CheckCircle2 className="size-3" />
            Ready
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center gap-3 py-2">
          <span className="flex size-9 items-center justify-center rounded-xl bg-cyan-300/10 text-cyan-200">
            <LoaderCircle className="size-4 animate-spin" />
          </span>
          <div>
            <p className="text-xs font-medium text-slate-200">
              Building repository index
            </p>
            <p className="mt-1 text-[11px] text-slate-500">
              Fetching source files and preparing search…
            </p>
          </div>
        </div>
      ) : error ? (
        <div className="flex items-start gap-2.5 rounded-xl border border-rose-400/15 bg-rose-400/[0.05] p-3 text-xs leading-5 text-rose-200">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : repository ? (
        <div>
          <p className="break-all text-sm font-semibold text-white">
            {repository.owner}/{repository.name}
          </p>
          <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
            <GitBranch className="size-3.5 text-slate-500" />
            <span className="truncate">{repository.branch}</span>
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs text-slate-400">
            <PackageOpen className="size-3.5 text-slate-500" />
            <span>{repository.files.length} source files indexed</span>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3 py-1">
          <span className="flex size-9 items-center justify-center rounded-xl bg-white/[0.04] text-slate-500">
            <PackageOpen className="size-4" />
          </span>
          <div>
            <p className="text-xs font-medium text-slate-300">
              No repository connected
            </p>
            <p className="mt-1 text-[11px] text-slate-600">
              Paste a GitHub URL above to begin.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

export default RepositoryStatus;
