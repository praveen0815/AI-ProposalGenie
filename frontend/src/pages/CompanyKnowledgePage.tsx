import { useCallback, useEffect, useState } from "react";
import type { DragEvent } from "react";
import { FileText, Library, RotateCcw, Trash2, Upload } from "lucide-react";
import { Link } from "react-router-dom";

import { buttonClasses } from "../components/ui/Button";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { PageHeader } from "../components/ui/PageHeader";
import { Spinner } from "../components/ui/Spinner";
import { useAuth } from "../context/AuthProvider";
import { useCompany } from "../context/CompanyProvider";
import { apiErrorMessage } from "../lib/apiError";
import { formatFileSize, formatTimestamp } from "../lib/format";
import { deleteDocument, listDocuments, reprocessDocument, uploadDocument } from "../services/knowledge";
import type { DocumentProcessingStatus, KnowledgeDocument } from "../types/knowledge";

const statusLabels: Record<DocumentProcessingStatus, string> = {
  UPLOADED: "Uploaded",
  PROCESSING: "Processing",
  COMPLETED: "Ready",
  FAILED: "Failed",
};

const statusClasses: Record<DocumentProcessingStatus, string> = {
  UPLOADED: "bg-slate-400/10 text-slate-200",
  PROCESSING: "bg-cyan-300/10 text-cyan-200",
  COMPLETED: "bg-emerald-400/10 text-emerald-300",
  FAILED: "bg-rose-400/10 text-rose-200",
};

export function CompanyKnowledgePage() {
  const { user } = useAuth();
  const { current, loading: companyLoading, error: companyError, refresh } = useCompany();
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const companyId = current?.id;

  const load = useCallback(async () => {
    if (!companyId) {
      setDocuments([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setDocuments(await listDocuments(companyId));
    } catch (caught) {
      setError(apiErrorMessage(caught, "Documents could not be loaded."));
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!documents.some((document) => document.processing_status === "PROCESSING" || document.processing_status === "UPLOADED")) {
      return;
    }
    const timer = window.setInterval(() => {
      void load();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [documents, load]);

  async function sendFile(file: File) {
    if (!companyId || progress !== null) {
      return;
    }
    setNotice(null);
    setError(null);
    setProgress(0);
    try {
      const saved = await uploadDocument(companyId, file, setProgress);
      setDocuments((currentDocuments) => [saved, ...currentDocuments.filter((item) => item.id !== saved.id)]);
      setNotice(
        saved.processing_status === "COMPLETED"
          ? `${saved.original_filename} is ready.`
          : `${saved.original_filename} could not be processed.`,
      );
    } catch (caught) {
      setError(apiErrorMessage(caught, "The file could not be uploaded."));
    } finally {
      setProgress(null);
    }
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 1) {
      setError("Upload one file at a time.");
      return;
    }
    const file = files[0];
    if (file) {
      void sendFile(file);
    }
  }

  async function retry(document: KnowledgeDocument) {
    setBusyId(document.id);
    setError(null);
    try {
      const updated = await reprocessDocument(document.id);
      setDocuments((currentDocuments) => currentDocuments.map((item) => (item.id === updated.id ? updated : item)));
    } catch (caught) {
      setError(apiErrorMessage(caught, "Processing could not be retried."));
    } finally {
      setBusyId(null);
    }
  }

  async function remove(document: KnowledgeDocument) {
    setBusyId(document.id);
    setError(null);
    try {
      await deleteDocument(document.id);
      setDocuments((currentDocuments) => currentDocuments.filter((item) => item.id !== document.id));
      setConfirmingId(null);
    } catch (caught) {
      setError(apiErrorMessage(caught, "The document could not be deleted."));
    } finally {
      setBusyId(null);
    }
  }

  if (companyLoading) {
    return <Spinner label="Loading company" />;
  }

  if (companyError) {
    return <ErrorState message={companyError} onRetry={() => void refresh()} />;
  }

  if (!current) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Sources"
          title="Company knowledge"
          description="Upload business documents for the company you are working in."
        />
        <EmptyState
          icon={Library}
          title="Create a company first"
          description="Documents belong to a company. Create one, then upload PDF, DOCX, TXT, or Markdown files."
          action={
            <Link to="/company/new" className={buttonClasses()}>
              Create company
            </Link>
          }
        />
      </div>
    );
  }

  const canManageAny = current.role === "OWNER" || current.role === "ADMIN";

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Sources"
        title="Company knowledge"
        description={`Files for ${current.name}. Extracted text stays on the server and is not shown in this list.`}
      />

      <Card>
        <label
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`flex cursor-pointer flex-col items-center rounded-2xl border border-dashed px-6 py-10 text-center ${
            dragging ? "border-cyan-300 bg-cyan-300/10" : "border-white/15 bg-white/[0.02]"
          }`}
        >
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-cyan-300/10 text-cyan-200">
            <Upload className="h-5 w-5" aria-hidden="true" />
          </span>
          <span className="mt-4 text-sm font-semibold text-white">Drop a document here, or browse</span>
          <span className="mt-2 max-w-md text-sm leading-6 text-slate-400">
            PDF, DOCX, TXT, and Markdown. The server checks the file contents and enforces the size limit.
          </span>
          <input
            type="file"
            className="sr-only"
            accept=".pdf,.docx,.txt,.md,.markdown,application/pdf,text/plain,text/markdown"
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = "";
              if (file) {
                void sendFile(file);
              }
            }}
          />
        </label>
        {progress !== null ? (
          <div className="mt-4">
            <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
              <div className="h-full bg-cyan-300 transition-all" style={{ width: `${progress}%` }} />
            </div>
            <p className="mt-2 text-xs text-slate-400">{progress < 100 ? `Uploading ${progress}%` : "Processing document"}</p>
          </div>
        ) : null}
      </Card>

      {notice ? <p className="text-sm text-cyan-100">{notice}</p> : null}
      {error ? <ErrorState title="Document request failed" message={error} /> : null}
      {loading && documents.length === 0 ? <Spinner label="Loading documents" /> : null}
      {!loading && documents.length === 0 && !error ? (
        <EmptyState
          icon={Library}
          title="No documents yet"
          description="Uploaded files for this company will appear here. Nothing is listed until you add one."
        />
      ) : null}

      {documents.length > 0 ? (
        <ul className="space-y-3">
          {documents.map((document) => {
            const canManage = canManageAny || document.uploaded_by_id === user?.id;
            return (
              <li key={document.id}>
                <Card className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <FileText className="h-4 w-4 text-cyan-200" aria-hidden="true" />
                      <h2 className="truncate text-sm font-semibold text-white">{document.original_filename}</h2>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusClasses[document.processing_status]}`}>
                        {statusLabels[document.processing_status]}
                      </span>
                    </div>
                    <p className="mt-2 text-sm text-slate-400">
                      {document.file_type} · {formatFileSize(document.file_size)}
                      {document.page_count ? ` · ${document.page_count} pages` : ""}
                      {document.character_count ? ` · ${document.character_count.toLocaleString()} characters extracted` : ""}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">Added {formatTimestamp(document.created_at)}</p>
                    {document.processing_error ? <p className="mt-2 text-sm text-rose-200">{document.processing_error}</p> : null}
                  </div>
                  {canManage ? (
                    <div className="flex flex-wrap gap-2">
                      {document.processing_status === "FAILED" ? (
                        <Button variant="secondary" disabled={busyId === document.id} onClick={() => void retry(document)}>
                          <RotateCcw className="h-4 w-4" aria-hidden="true" />
                          Retry processing
                        </Button>
                      ) : null}
                      {confirmingId === document.id ? (
                        <>
                          <Button variant="secondary" disabled={busyId === document.id} onClick={() => setConfirmingId(null)}>
                            Cancel
                          </Button>
                          <Button disabled={busyId === document.id} onClick={() => void remove(document)}>
                            Confirm delete
                          </Button>
                        </>
                      ) : (
                        <Button variant="ghost" onClick={() => setConfirmingId(document.id)}>
                          <Trash2 className="h-4 w-4" aria-hidden="true" />
                          Delete
                        </Button>
                      )}
                    </div>
                  ) : null}
                </Card>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
