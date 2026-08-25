import { useEffect, useRef, useState } from "react";
import { Bot, Square } from "lucide-react";
import { streamChatTurn } from "../../api/client";
import { CitedAnswer, ErrorNotice, StatusBadge } from "../Common";
import { useBufferedStream } from "../../hooks/useBufferedStream";
import type { Citation, GenerationResult } from "../../types";

export interface PendingTurn { clientTurnId: string; query: string; documentIds: string[] | null; }

export function StreamingTurn({ sessionId, turn, onCitation, onSettled }: { sessionId: string; turn: PendingTurn; onCitation: (citation: Citation) => void; onSettled: () => Promise<void>; }) {
  const [phase, setPhase] = useState("connecting");
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const controller = useRef<AbortController | null>(null);
  const { visibleText, append, finish, reset, stats } = useBufferedStream();

  useEffect(() => {
    const abortController = new AbortController();
    controller.current = abortController;
    reset();
    void streamChatTurn(sessionId, { client_turn_id: turn.clientTurnId, query: turn.query, document_ids: turn.documentIds }, {
      start: () => setPhase("streaming"),
      delta: append,
      done: (value) => { finish(value.answer_text); setResult(value); setPhase("done"); window.setTimeout(() => void onSettled(), 0); },
      error: (value) => { setError(new Error(String(value.safe_message ?? "Provider stream failed"))); setPhase("error"); window.setTimeout(() => void onSettled(), 0); },
    }, abortController.signal).catch((value: unknown) => {
      if ((value as Error).name === "AbortError") { setPhase("cancelled"); window.setTimeout(() => void onSettled(), 150); }
      else { setError(value); setPhase("error"); window.setTimeout(() => void onSettled(), 0); }
    });
    return () => abortController.abort();
  }, [append, finish, onSettled, reset, sessionId, turn]);

  return (
    <article className="mb-7 flex gap-3" aria-live="polite">
      <span className="mt-1 grid h-7 w-7 flex-none place-items-center rounded-md bg-blue-600 text-white" aria-hidden="true"><Bot size={14} /></span>
      <div className="min-w-0 flex-1">
        <header className="mb-2 flex items-center justify-between gap-3"><div className="flex items-center gap-2"><strong className="text-xs font-semibold text-blue-700">Lexicon AI</strong><StatusBadge value={result?.status ?? phase} /></div>{["connecting", "streaming"].includes(phase) ? <button className="gap-1 border-slate-200 bg-white px-2 py-1 text-xs text-slate-600" aria-label="Stop generation" onClick={() => controller.current?.abort()}><Square size={12} /> Stop</button> : null}</header>
        <ErrorNotice error={error} />
        {!visibleText && phase === "connecting" ? <div className="loading">Initializing persistent turn…</div> : null}
        {!visibleText && phase === "streaming" ? <div className="loading">Preparing the first grounded token…</div> : null}
        {visibleText ? <CitedAnswer text={visibleText} citations={result?.citations ?? []} onCitation={onCitation} /> : null}
        {import.meta.env.DEV && stats.incomingDeltas ? <details className="stream-diagnostics"><summary>Streaming diagnostics</summary><span>{stats.incomingDeltas} provider deltas → {stats.visibleCommits} visible commits · {stats.cadenceMs} ms cadence</span></details> : null}
      </div>
    </article>
  );
}
