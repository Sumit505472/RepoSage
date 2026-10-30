import { useRef, useState } from "react";
import {
  ArrowUpRight,
  Check,
  Code2,
  GitBranch,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import ChatInput from "./components/ChatInput.jsx";
import ChatWindow from "./components/ChatWindow.jsx";
import RepositoryInput from "./components/RepositoryInput.jsx";
import RepositoryStatus from "./components/RepositoryStatus.jsx";
import Sidebar from "./components/Sidebar.jsx";
import { askRepository, indexRepository } from "./services/api.js";

const STARTER_QUESTIONS = [
  "How is the project structured?",
  "Where does the main functionality live?",
  "What should I know before contributing?",
];

function createMessageId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

function App() {
  const [repositoryUrl, setRepositoryUrl] = useState("");
  const [repository, setRepository] = useState(null);
  const [indexing, setIndexing] = useState(false);
  const [indexError, setIndexError] = useState("");
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const requestInFlight = useRef(false);

  async function handleIndex(event) {
    event.preventDefault();
    const url = repositoryUrl.trim();
    if (!url || requestInFlight.current) return;

    requestInFlight.current = true;
    setIndexing(true);
    setIndexError("");
    setRepository(null);
    setMessages([]);

    try {
      const indexedRepository = await indexRepository(url);
      setRepository({
        owner: indexedRepository.owner,
        name: indexedRepository.name,
        branch: indexedRepository.branch,
        files: indexedRepository.files.map(({ path, language }) => ({
          path,
          language,
        })),
        repositoryUrl: url,
      });
    } catch (error) {
      setIndexError(error.message);
    } finally {
      requestInFlight.current = false;
      setIndexing(false);
    }
  }

  function handleRepositoryUrlChange(value) {
    setRepositoryUrl(value);
    setIndexError("");
    if (repository) {
      setRepository(null);
      setMessages([]);
    }
  }

  async function handleAsk(event) {
    event.preventDefault();
    const submittedQuestion = question.trim();
    if (!repository || !submittedQuestion || requestInFlight.current) return;

    requestInFlight.current = true;
    setQuestion("");
    const messageId = createMessageId();
    setMessages((current) => [
      ...current,
      { id: messageId, question: submittedQuestion, status: "loading" },
    ]);

    try {
      const answer = await askRepository(
        repository.repositoryUrl,
        submittedQuestion,
      );
      setMessages((current) =>
        current.map((message) =>
          message.id === messageId
            ? { ...message, status: "complete", answer }
            : message,
        ),
      );
    } catch (error) {
      setMessages((current) =>
        current.map((message) =>
          message.id === messageId
            ? { ...message, status: "error", error: error.message }
            : message,
        ),
      );
    } finally {
      requestInFlight.current = false;
    }
  }

  return (
    <div className="min-h-screen bg-[#080b12] text-slate-100 selection:bg-cyan-400/30">
      <div className="mx-auto flex min-h-screen max-w-[1680px] flex-col lg:flex-row">
        <Sidebar>
          <RepositoryInput
            value={repositoryUrl}
            onChange={handleRepositoryUrlChange}
            onSubmit={handleIndex}
            isLoading={indexing}
            disabled={requestInFlight.current && !indexing}
          />
          <RepositoryStatus
            repository={repository}
            isLoading={indexing}
            error={indexError}
          />
          <div className="mt-auto hidden rounded-2xl border border-white/[0.07] bg-white/[0.025] p-4 lg:block">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
              <ShieldCheck className="size-4 text-emerald-400" />
              Your code stays yours
            </div>
            <p className="mt-2 text-xs leading-5 text-slate-500">
              Only retrieved code snippets are sent to the configured AI
              provider to answer a question.
            </p>
          </div>
        </Sidebar>

        <main className="flex min-h-screen min-w-0 flex-1 flex-col">
          <header className="flex h-[68px] shrink-0 items-center justify-between border-b border-white/[0.07] px-5 sm:px-8">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Code2 className="size-4" />
              <span className="hidden sm:inline">Workspace</span>
              <span className="text-slate-700">/</span>
              <span className="max-w-[170px] truncate font-medium text-slate-300">
                {repository
                  ? `${repository.owner}/${repository.name}`
                  : "New conversation"}
              </span>
            </div>
            <div className="flex items-center gap-2 rounded-full border border-emerald-400/15 bg-emerald-400/[0.06] px-2.5 py-1.5 text-[10px] font-medium text-emerald-300 sm:px-3 sm:text-[11px]">
              <span className="size-1.5 rounded-full bg-emerald-400" />
              <span className="hidden sm:inline">Grounded AI chat</span>
              <span className="sm:hidden">AI</span>
            </div>
          </header>

          <section className="flex min-h-0 flex-1 flex-col">
            <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-4 sm:px-8">
              {messages.length === 0 ? (
                <div className="flex flex-1 flex-col items-center justify-center py-14 text-center">
                  <div className="mb-6 flex size-16 items-center justify-center rounded-[22px] border border-cyan-300/15 bg-gradient-to-br from-cyan-400/15 to-blue-500/10 shadow-[0_0_60px_-20px_rgba(34,211,238,0.28)]">
                    <Sparkles className="size-7 text-cyan-200" />
                  </div>
                  <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] font-medium tracking-wide text-slate-400">
                    <span className="size-1.5 rounded-full bg-cyan-300" />
                    REPOSITORY-AWARE ASSISTANT
                  </div>
                  <h1 className="max-w-2xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                    Understand any codebase,
                    <span className="block bg-gradient-to-r from-cyan-200 to-blue-300 bg-clip-text text-transparent">
                      one question at a time.
                    </span>
                  </h1>
                  <p className="mt-4 max-w-lg text-sm leading-6 text-slate-400 sm:text-base">
                    Connect a public GitHub repository, then ask questions and
                    get answers grounded in its source code.
                  </p>

                  <div className="mt-9 grid w-full max-w-2xl gap-2 sm:grid-cols-3">
                    {STARTER_QUESTIONS.map((starterQuestion) => (
                      <button
                        key={starterQuestion}
                        type="button"
                        disabled={!repository || indexing}
                        onClick={() => setQuestion(starterQuestion)}
                        className="group flex min-h-20 items-start justify-between gap-3 rounded-xl border border-white/[0.08] bg-white/[0.025] p-4 text-left text-xs leading-5 text-slate-400 transition hover:border-cyan-300/25 hover:bg-cyan-300/[0.04] hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <span>{starterQuestion}</span>
                        <ArrowUpRight className="mt-0.5 size-3.5 shrink-0 text-slate-600 transition group-hover:text-cyan-200" />
                      </button>
                    ))}
                  </div>
                  {!repository && (
                    <p className="mt-4 text-xs text-slate-600">
                      Index a repository in the sidebar to get started.
                    </p>
                  )}
                  {repository && (
                    <p className="mt-4 flex items-center gap-1.5 text-xs text-emerald-300/80">
                      <Check className="size-3.5" />
                      Repository ready — choose a prompt or ask below
                    </p>
                  )}
                </div>
              ) : (
                <ChatWindow messages={messages} repository={repository} />
              )}
            </div>
            <div className="sticky bottom-0 border-t border-white/[0.06] bg-[#080b12]/95 px-4 pb-4 pt-3 backdrop-blur-xl sm:px-8 sm:pb-6">
              <div className="mx-auto max-w-4xl">
                <ChatInput
                  value={question}
                  onChange={setQuestion}
                  onSubmit={handleAsk}
                  disabled={!repository || indexing}
                  isLoading={messages.some(
                    (message) => message.status === "loading",
                  )}
                />
                <p className="mt-2 text-center text-[10px] text-slate-600">
                  RepoSage can make mistakes. Verify answers against the cited
                  source.
                </p>
              </div>
            </div>
          </section>
          <footer className="flex items-center justify-center gap-1.5 border-t border-white/[0.05] py-2.5 text-[10px] text-slate-600">
            <GitBranch className="size-3" />
            Built for developers who like to understand the why
          </footer>
        </main>
      </div>
    </div>
  );
}

export default App;
