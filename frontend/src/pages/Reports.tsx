import { useState } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { ErrorBox, Loading, PageHeader, SeverityBadge, Stat } from "../components/ui";
import type { ReportResponse } from "../types";

export default function Reports() {
  const { datasetId = "" } = useParams();
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate() {
    setLoading(true);
    setError(null);
    try {
      setReport(await api.report(datasetId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Report generation failed.");
    } finally {
      setLoading(false);
    }
  }

  function download() {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `datasleuth-report-${datasetId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      <PageHeader
        title="Reports"
        subtitle="A summary of quality findings, statistics, business-rule violations and recommendations."
        actions={
          <div className="flex gap-2">
            <button className="btn-primary" onClick={generate} disabled={loading}>{report ? "Regenerate" : "Generate report"}</button>
            {report && <button className="btn-ghost" onClick={download}>Download JSON</button>}
          </div>
        }
      />
      {loading && <Loading label="Generating…" />}
      {error && <ErrorBox message={error} />}
      {report && (
        <div className="space-y-10">
          <div className="grid gap-4 md:grid-cols-4">
            <Stat label="Rows" value={Number(report.overview.row_count).toLocaleString()} />
            <Stat label="Columns" value={String(report.overview.column_count)} />
            <Stat label="Quality findings" value={report.quality_findings.length} />
            <Stat label="Rule violations" value={report.business_rule_violations.length} />
          </div>

          <section>
            <h2 className="mb-3 text-2xl font-semibold">Quality findings</h2>
            <div className="grid gap-3">
              {report.quality_findings.map((f) => (
                <div key={f.finding_id} className="card flex items-start justify-between gap-4">
                  <p className="text-sm">{f.description}</p>
                  <SeverityBadge level={f.severity} />
                </div>
              ))}
              {report.quality_findings.length === 0 && <div className="card text-sm text-muted">None.</div>}
            </div>
          </section>

          <section>
            <h2 className="mb-3 text-2xl font-semibold">Statistical observations</h2>
            <ul className="card space-y-2 text-sm">
              {report.statistical_observations.map((o) => <li key={o}>{o}</li>)}
            </ul>
          </section>

          <section>
            <h2 className="mb-3 text-2xl font-semibold">Business-rule violations</h2>
            <div className="grid gap-3">
              {report.business_rule_violations.map((f) => (
                <div key={f.finding_id} className="card text-sm">{f.description}</div>
              ))}
              {report.business_rule_violations.length === 0 && (
                <div className="card text-sm text-muted">No violations of the evaluated rules, or no rules document uploaded.</div>
              )}
            </div>
          </section>

          <section>
            <h2 className="mb-3 text-2xl font-semibold">Recommendations</h2>
            <ol className="card list-decimal space-y-2 pl-10 text-sm">
              {report.recommendations.map((r) => <li key={r}>{r}</li>)}
            </ol>
          </section>
        </div>
      )}
    </>
  );
}
