import { BookOpen, GitBranch, Sparkles } from "lucide-react";

function Sidebar({ children }) {
  return (
    <aside className="flex w-full shrink-0 flex-col border-b border-white/[0.07] bg-[#0c1018] px-5 py-5 lg:sticky lg:top-0 lg:h-screen lg:w-[340px] lg:border-b-0 lg:border-r lg:px-6 lg:py-7">
      <a href="/" className="flex items-center gap-3">
        <span className="flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-300 to-blue-500 text-slate-950 shadow-lg shadow-cyan-500/10">
          <Sparkles className="size-5" />
        </span>
        <span>
          <span className="block text-base font-semibold tracking-tight text-white">
            RepoSage
          </span>
          <span className="block text-[10px] font-medium uppercase tracking-[0.16em] text-slate-500">
            Codebase intelligence
          </span>
        </span>
      </a>

      <div className="mb-3 mt-8 flex items-center justify-between">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
          Repository
        </h2>
        <GitBranch className="size-4 text-slate-600" />
      </div>

      {children}

      <div className="mt-5 hidden items-center gap-2 border-t border-white/[0.06] pt-4 text-[11px] text-slate-600 lg:flex">
        <BookOpen className="size-3.5" />
        <span>Answers are grounded in retrieved source</span>
      </div>
    </aside>
  );
}

export default Sidebar;
