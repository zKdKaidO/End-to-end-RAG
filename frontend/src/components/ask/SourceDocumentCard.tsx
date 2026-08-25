import type { DocumentPipeline } from "../../types";

export function SourceDocumentCard({ document, selected, onToggle }: {
  document: DocumentPipeline;
  selected: boolean;
  onToggle: (documentId: string) => void;
}) {
  return (
    <label className={`flex cursor-pointer items-start gap-2 rounded-lg border p-3 text-left ${selected ? "border-blue-300 bg-blue-50" : "border-slate-200 bg-white"}`}>
      <input type="checkbox" className="mt-0.5 h-4 w-4 flex-none accent-blue-600" checked={selected} onChange={() => onToggle(document.document_id)} aria-label={`Include ${document.filename}`} />
      <span className="min-w-0">
        <span className="mb-1 block text-[9px] font-semibold uppercase tracking-wider text-blue-600">Document</span>
        <strong className="block truncate text-xs text-slate-700">{document.filename}</strong>
        <small className="mt-1 block text-[10px] text-slate-400">{document.page_count} pages · {document.chunk_count} chunks</small>
      </span>
    </label>
  );
}
