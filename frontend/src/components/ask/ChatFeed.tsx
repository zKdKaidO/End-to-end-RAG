import { Bot } from "lucide-react";
import { CitedAnswer, StatusBadge } from "../Common";
import type { ChatMessage, Citation } from "../../types";

export function ChatFeed({ messages, pendingTurn, hasOlder, onLoadOlder, onCitation, onSources, onRetry }: {
  messages: ChatMessage[];
  pendingTurn?: React.ReactNode;
  hasOlder: boolean;
  onLoadOlder: () => void;
  onCitation: (citation: Citation) => void;
  onSources: (citations: Citation[]) => void;
  onRetry: (message: ChatMessage) => void;
}) {
  return (
    <section className="h-full overflow-y-auto px-4 py-6 sm:px-6" aria-label="Conversation history">
      <div className="mx-auto max-w-3xl">
        {hasOlder ? <button className="mx-auto mb-4 flex border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600" onClick={onLoadOlder}>Load older messages</button> : null}
        {!messages.length && !pendingTurn ? <WelcomeMessage /> : null}
        {messages.map((message) => message.role === "USER" ? <UserMessage key={message.id} text={message.content} /> : <AssistantMessage key={message.id} message={message} onCitation={onCitation} onSources={onSources} onRetry={() => onRetry(message)} />)}
        {pendingTurn}
      </div>
    </section>
  );
}

function WelcomeMessage() {
  return <div className="flex gap-3 py-3"><span className="mt-1 grid h-7 w-7 flex-none place-items-center rounded-md bg-blue-600 text-white" aria-hidden="true"><Bot size={14} /></span><div className="max-w-xl text-sm leading-6 text-slate-600"><strong className="mb-1 block text-xs font-semibold text-blue-700">Lexicon AI</strong><p className="m-0">Good morning. I’m ready to help research your indexed Vietnamese legal corpus. Ask a question, review the cited evidence, or narrow the research scope to specific documents.</p></div></div>;
}

export function UserMessage({ text }: { text: string }) {
  return <article className="mb-6 ml-auto max-w-[75%] rounded-2xl rounded-br-md bg-blue-600 px-4 py-3 text-sm leading-6 text-white"><p className="m-0 whitespace-pre-wrap">{text}</p></article>;
}

export function AssistantMessage({ message, onCitation, onSources, onRetry }: { message: ChatMessage; onCitation: (citation: Citation) => void; onSources: (citations: Citation[]) => void; onRetry: () => void }) {
  const terminalFailure = message.delivery_state === "FAILED" || message.delivery_state === "CANCELLED";
  return (
    <article className={`mb-7 flex gap-3 ${terminalFailure ? "opacity-80" : ""}`}>
      <span className="mt-1 grid h-7 w-7 flex-none place-items-center rounded-md bg-blue-600 text-white" aria-hidden="true"><Bot size={14} /></span>
      <div className="min-w-0 flex-1">
        <header className="mb-2 flex items-center justify-between gap-3"><strong className="text-xs font-semibold text-blue-700">Lexicon AI</strong><StatusBadge value={message.failure_code === "ORPHANED_STREAM_TIMEOUT" ? "INTERRUPTED" : message.answer_status ?? message.delivery_state} /></header>
        {terminalFailure ? <div className="notice warning"><span>{message.failure_detail_safe ?? "Incomplete response."}</span><button className="compact-button" onClick={onRetry}>Retry</button></div> : null}
        {message.content ? <CitedAnswer text={message.content} citations={message.citations} onCitation={onCitation} /> : null}
        {!terminalFailure && message.answer_status === "INSUFFICIENT_EVIDENCE" ? <div className="notice warning">The selected evidence did not support the exact requested fact.</div> : null}
        <footer className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-slate-100 pt-2 text-[10px] text-slate-400"><button className="border-0 bg-transparent p-0 text-[10px] font-medium text-blue-600 disabled:text-slate-400" disabled={!message.citations.length} onClick={() => onSources(message.citations)}>{message.citations.length} {message.citations.length === 1 ? "source" : "sources"}</button><span>{message.model_id ?? "No model result"}</span><span>{message.prompt_version ?? "—"}</span></footer>
      </div>
    </article>
  );
}
