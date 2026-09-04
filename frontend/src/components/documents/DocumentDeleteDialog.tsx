import { AlertTriangle, X } from "lucide-react";
import type { DocumentPipeline } from "../../types";
import "./DocumentDeleteDialog.css";

interface DocumentDeleteDialogProps {
  document: DocumentPipeline | null;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function DocumentDeleteDialog({ document, pending, onCancel, onConfirm }: DocumentDeleteDialogProps) {
  if (!document) {
    return null;
  }

  return (
    <div
      className="zkd-delete-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !pending) {
          onCancel();
        }
      }}
    >
      <div
        className="zkd-delete-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="zkd-delete-title"
        aria-describedby="zkd-delete-description"
      >
        <button
          type="button"
          className="zkd-delete-close"
          aria-label="Close"
          disabled={pending}
          onClick={onCancel}
        >
          <X size={17} />
        </button>

        <div className="zkd-delete-icon">
          <AlertTriangle size={24} strokeWidth={2} />
        </div>

        <h2 id="zkd-delete-title">
          Remove document?
        </h2>

        <p id="zkd-delete-description">
          <strong>{document.filename}</strong> will be removed from your library.
          Any document data that is no longer required by another valid access
          scope will also be cleaned up.
        </p>

        <div className="zkd-delete-actions">
          <button
            type="button"
            className="zkd-delete-cancel"
            disabled={pending}
            onClick={onCancel}
          >
            Cancel
          </button>

          <button
            type="button"
            className="zkd-delete-confirm"
            disabled={pending}
            onClick={onConfirm}
          >
            {pending ? "Removing…" : "Remove"}
          </button>
        </div>
      </div>
    </div>
  );
}