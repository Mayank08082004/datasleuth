import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { ErrorBox, Loading, PageHeader, Stat } from "../components/ui";
import { useAsync } from "../hooks";

export default function Dashboard() {
  const navigate = useNavigate();
  const { data, error, loading, reload } = useAsync(() => api.listDatasets(), []);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  async function onUpload(e: FormEvent<HTMLInputElement>) {
    const file = e.currentTarget.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      const meta = await api.uploadDataset(file);
      navigate(`/datasets/${meta.dataset_id}`);
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : "Upload failed.");
      reload();
    } finally {
      setUploading(false);
    }
  }

  const datasets = data?.datasets ?? [];
  const totalRows = datasets.reduce((s, d) => s + d.row_count, 0);

  return (
    <>
      <PageHeader
        title="Welcome to DataSleuth"
        subtitle="Upload a CSV or Excel dataset to profile it, audit its quality and ask questions with evidence-backed answers."
      />

      <div className="grid gap-6 md:grid-cols-3">
        <div className="card md:col-span-2">
          <div className="label">Upload a dataset</div>
          <p className="mt-2 text-sm text-muted">CSV or XLSX, up to the server's configured size limit.</p>
          <label className="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-line bg-canvas px-6 py-10 text-center hover:border-amber">
            <span className="font-semibold">{uploading ? "Uploading…" : "Choose a file"}</span>
            <span className="mt-1 text-xs text-muted">.csv or .xlsx</span>
            <input type="file" accept=".csv,.xlsx" className="hidden" disabled={uploading} onChange={onUpload} />
          </label>
          {uploadError && <div className="mt-4"><ErrorBox message={uploadError} /></div>}
        </div>
        <div className="grid gap-6">
          <Stat label="Datasets" value={datasets.length} />
          <Stat label="Total rows" value={totalRows.toLocaleString()} />
        </div>
      </div>

      <section className="mt-10">
        <h2 className="mb-4 text-2xl font-semibold">Recent datasets</h2>
        {loading && <Loading />}
        {error && <ErrorBox message={error} />}
        {!loading && !error && datasets.length === 0 && (
          <div className="card text-sm text-muted">No datasets yet. Upload one to get started.</div>
        )}
        <div className="grid gap-4 md:grid-cols-2">
          {datasets.map((d) => (
            <Link key={d.dataset_id} to={`/datasets/${d.dataset_id}`} className="card transition hover:-translate-y-0.5">
              <div className="flex items-center justify-between">
                <span className="font-semibold">{d.filename}</span>
                <span className="mono uppercase text-muted">{d.file_type}</span>
              </div>
              <div className="mt-2 text-sm text-muted">
                {d.row_count.toLocaleString()} rows · {d.column_count} columns
              </div>
              <div className="mono mt-3 text-muted">{new Date(d.created_at).toLocaleString()}</div>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
