import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { ErrorBox, Loading, PageHeader, Stat, formatNumber } from "../components/ui";
import { useAsync } from "../hooks";

const PAGE_SIZE = 20;

export default function DatasetOverview() {
  const { datasetId = "" } = useParams();
  const meta = useAsync(() => api.getDataset(datasetId), [datasetId]);
  const profile = useAsync(() => api.profile(datasetId), [datasetId]);
  const [page, setPage] = useState(1);
  const preview = useAsync(() => api.preview(datasetId, page, PAGE_SIZE), [datasetId, page]);

  if (meta.loading) return <Loading />;
  if (meta.error) return <ErrorBox message={meta.error} />;
  const d = meta.data!;
  const totalPages = preview.data ? Math.max(1, Math.ceil(preview.data.total_rows / PAGE_SIZE)) : 1;

  return (
    <>
      <PageHeader title={d.filename} subtitle={`${d.file_type.toUpperCase()} · uploaded ${new Date(d.created_at).toLocaleString()}`} />

      <div className="grid gap-4 md:grid-cols-4">
        <Stat label="Rows" value={d.row_count.toLocaleString()} />
        <Stat label="Columns" value={d.column_count} />
        <Stat label="Missing cells" value={profile.data ? profile.data.missing_cells.toLocaleString() : "…"} />
        <Stat label="Duplicate rows" value={profile.data ? profile.data.duplicate_rows.toLocaleString() : "…"} />
      </div>

      <section className="mt-10">
        <h2 className="mb-4 text-2xl font-semibold">Column summaries</h2>
        {profile.loading && <Loading />}
        {profile.error && <ErrorBox message={profile.error} />}
        <div className="grid gap-4 md:grid-cols-2">
          {profile.data?.columns.map((c) => (
            <div key={c.name} className="card">
              <div className="flex items-center justify-between">
                <span className="mono text-sm font-semibold">{c.name}</span>
                <span className="rounded-full bg-canvas px-2.5 py-0.5 text-xs font-semibold capitalize text-muted">{c.kind}</span>
              </div>
              <div className="mono mt-1 text-muted">{c.dtype}</div>
              {c.kind === "numeric" && c.stats && (
                <dl className="mt-3 grid grid-cols-3 gap-2 text-sm">
                  {(["mean", "median", "min", "max", "std", "iqr"] as const).map((k) => (
                    <div key={k}>
                      <dt className="label">{k}</dt>
                      <dd>{formatNumber((c.stats as Record<string, unknown>)[k])}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {c.kind === "date" && c.stats && (
                <div className="mt-3 text-sm">
                  {String((c.stats as Record<string, unknown>).earliest)} → {String((c.stats as Record<string, unknown>).latest)}
                </div>
              )}
              {c.kind === "categorical" && c.stats && (
                <ul className="mt-3 space-y-1 text-sm">
                  {((c.stats as { top_values: { value: string; count: number }[] }).top_values ?? []).slice(0, 4).map((t) => (
                    <li key={t.value} className="flex justify-between">
                      <span className="truncate">{t.value}</span>
                      <span className="mono text-muted">{t.count}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="mt-10">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-2xl font-semibold">Data preview</h2>
          <div className="flex items-center gap-2 text-sm">
            <button className="btn-ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Previous</button>
            <span className="text-muted">Page {page} of {totalPages}</span>
            <button className="btn-ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        </div>
        {preview.loading && <Loading />}
        {preview.error && <ErrorBox message={preview.error} />}
        {preview.data && (
          <div className="card overflow-x-auto p-0">
            <table className="min-w-full text-sm">
              <thead className="bg-canvas">
                <tr>
                  {preview.data.columns.map((c) => (
                    <th key={c} className="label whitespace-nowrap px-4 py-3 text-left">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.data.rows.map((row, i) => (
                  <tr key={i} className="border-t border-line">
                    {preview.data!.columns.map((c) => (
                      <td key={c} className="whitespace-nowrap px-4 py-2">{row[c] == null ? <span className="text-muted">—</span> : String(row[c])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
