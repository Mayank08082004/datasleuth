import { useParams } from "react-router-dom";
import { api } from "../api";
import { ErrorBox, Loading, PageHeader, SeverityBadge, Stat } from "../components/ui";
import { useAsync } from "../hooks";
import type { Finding } from "../types";

const GROUPS: { key: string; title: string; match: (f: Finding) => boolean }[] = [
  { key: "missing", title: "Missing values", match: (f) => f.category === "missing_values" },
  { key: "dups", title: "Duplicates", match: (f) => f.category.startsWith("duplicate") },
  { key: "invalid", title: "Invalid values", match: (f) => f.category.startsWith("invalid") || f.category === "unexpected_category" },
  { key: "outliers", title: "Outliers (need investigation)", match: (f) => f.category === "statistical_outlier" },
  { key: "rules", title: "Business-rule violations", match: (f) => f.category === "business_rule_violation" },
];

function FindingCard({ f }: { f: Finding }) {
  return (
    <div className="card">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="mono text-muted">{f.finding_id}{f.column ? ` · ${f.column}` : ""}</div>
          <p className="mt-1 font-semibold">{f.description}</p>
        </div>
        <SeverityBadge level={f.severity} />
      </div>
      <div className="mt-3 text-sm">
        <span className="label mr-2">Affected records</span>{f.affected_records}
      </div>
      {Object.keys(f.evidence).length > 0 && (
        <pre className="mono mt-3 overflow-x-auto rounded-xl bg-canvas p-3 text-muted">{JSON.stringify(f.evidence, null, 2)}</pre>
      )}
      <div className="mt-3 text-sm"><span className="label mr-2">Recommended</span>{f.recommended_action}</div>
      {f.needs_investigation && (
        <div className="mt-2 text-xs text-muted">May be legitimate; investigate before treating as an error.</div>
      )}
    </div>
  );
}

export default function DataQuality() {
  const { datasetId = "" } = useParams();
  const { data, error, loading } = useAsync(() => api.quality(datasetId), [datasetId]);

  const findings = data?.findings ?? [];
  const high = findings.filter((f) => f.severity === "high").length;
  const medium = findings.filter((f) => f.severity === "medium").length;

  return (
    <>
      <PageHeader title="Data quality" subtitle="Deterministic checks run in Python on your original and normalised data. Nothing is modified." />
      {loading && <Loading label="Running checks…" />}
      {error && <ErrorBox message={error} />}
      {data && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Stat label="Findings" value={findings.length} />
            <Stat label="High severity" value={high} />
            <Stat label="Medium severity" value={medium} />
          </div>

          {GROUPS.map((g) => {
            const items = findings.filter(g.match);
            if (items.length === 0) return null;
            return (
              <section key={g.key} className="mt-10">
                <h2 className="mb-4 text-2xl font-semibold">{g.title}</h2>
                <div className="grid gap-4">{items.map((f) => <FindingCard key={f.finding_id} f={f} />)}</div>
              </section>
            );
          })}

          {findings.length === 0 && <div className="card mt-8 text-sm text-muted">No quality findings for this dataset.</div>}

          {data.unsupported_rules.length > 0 && (
            <section className="mt-10">
              <h2 className="mb-2 text-2xl font-semibold">Rules not evaluated</h2>
              <p className="mb-4 text-sm text-muted">These statements did not match a supported rule pattern, so they were not guessed at.</p>
              <ul className="space-y-2">
                {data.unsupported_rules.map((u) => (
                  <li key={u.rule} className="card text-sm">{u.rule}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </>
  );
}
