import { useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { ErrorBox, Loading, PageHeader } from "../components/ui";
import { useAsync } from "../hooks";

export default function Documentation() {
  const { datasetId = "" } = useParams();
  const docs = useAsync(() => api.listDocuments(datasetId), [datasetId]);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  async function onUpload(e: FormEvent<HTMLInputElement>) {
    const file = e.currentTarget.files?.[0];
    e.currentTarget.value = "";
    if (!file) return;
    setUploading(true);
    setMessage(null);
    try {
      const meta = await api.uploadDocument(datasetId, file);
      setMessage({ kind: "ok", text: `Indexed "${meta.filename}" as ${meta.document_type.replace("_", " ")} (${meta.chunk_count} chunks).` });
      docs.reload();
    } catch (err) {
      setMessage({ kind: "err", text: err instanceof ApiError ? err.message : "Upload failed." });
    } finally {
      setUploading(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Documentation"
        subtitle="Upload data dictionaries, business rules, or dataset descriptions (TXT, Markdown or PDF). They are indexed for this dataset only."
      />

      <div className="card">
        <div className="label">Upload a document</div>
        <label className="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-line bg-canvas px-6 py-8 text-center hover:border-amber">
          <span className="font-semibold">{uploading ? "Indexing…" : "Choose a file"}</span>
          <span className="mt-1 text-xs text-muted">.txt, .md or .pdf · name it with "dictionary" or "rules" to classify it</span>
          <input type="file" accept=".txt,.md,.pdf" className="hidden" disabled={uploading} onChange={onUpload} />
        </label>
        {message && (
          <div className="mt-4">
            {message.kind === "ok"
              ? <div className="rounded-xl bg-sage-soft px-4 py-3 text-sm">{message.text}</div>
              : <ErrorBox message={message.text} />}
          </div>
        )}
      </div>

      <section className="mt-10">
        <h2 className="mb-4 text-2xl font-semibold">Uploaded documents</h2>
        {docs.loading && <Loading />}
        {docs.error && <ErrorBox message={docs.error} />}
        {docs.data && docs.data.documents.length === 0 && (
          <div className="card text-sm text-muted">No documents uploaded for this dataset yet.</div>
        )}
        <div className="grid gap-3">
          {docs.data?.documents.map((d) => (
            <div key={d.document_id} className="card flex items-center justify-between">
              <div>
                <div className="font-semibold">{d.filename}</div>
                <div className="mono mt-1 text-muted">{d.document_type.replace("_", " ")} · {d.chunk_count} chunks · {new Date(d.created_at).toLocaleString()}</div>
              </div>
              <span className="rounded-full bg-sage-soft px-2.5 py-0.5 text-xs font-semibold text-sage">Indexed</span>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
