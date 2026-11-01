import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import ChartView from "../components/ChartView";
import { ErrorBox, Loading, PageHeader } from "../components/ui";
import { useAsync } from "../hooks";
import type { ChatResponse } from "../types";

const SUGGESTIONS = [
  "Which columns have missing values?",
  "Are there duplicate records?",
  "What is the average amount by region?",
  "Show monthly revenue",
  "Find unusually large transactions",
  "Show the relationship between quantity and amount",
  "Does this dataset violate the uploaded business rules?",
  "What does the data dictionary say about region?",
];

interface Turn {
  question: string;
  response?: ChatResponse;
  error?: string;
}

export default function Ask() {
  const { datasetId = "" } = useParams();
  const navigate = useNavigate();
  const datasets = useAsync(() => api.listDatasets(), []);
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [pending, setPending] = useState(false);

  async function ask(question: string) {
    const q = question.trim();
    if (q.length < 3 || pending) return;
    setInput("");
    setPending(true);
    setTurns((t) => [...t, { question: q }]);
    try {
      const response = await api.chat(datasetId, q);
      setTurns((t) => [...t.slice(0, -1), { question: q, response }]);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "The request failed. Check the backend is running.";
      setTurns((t) => [...t.slice(0, -1), { question: q, error: message }]);
    } finally {
      setPending(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void ask(input);
  }

  return (
    <>
      <PageHeader
        title="Ask DataSleuth"
        subtitle="Questions are answered by Python tools. The explanation is generated only from their computed results."
        actions={
          datasets.data && (
            <select
              aria-label="Dataset"
              className="input w-64"
              value={datasetId}
              onChange={(e) => navigate(`/datasets/${e.target.value}/ask`)}
            >
              {datasets.data.datasets.map((d) => (
                <option key={d.dataset_id} value={d.dataset_id}>{d.filename}</option>
              ))}
            </select>
          )
        }
      />

      <div className="mb-6 flex flex-wrap gap-2">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="btn-ghost text-xs" disabled={pending} onClick={() => void ask(s)}>{s}</button>
        ))}
      </div>

      <div className="space-y-6">
        {turns.length === 0 && <div className="card text-sm text-muted">Ask a question about this dataset, or pick a suggestion.</div>}
        {turns.map((t, i) => (
          <div key={i} className="space-y-3">
            <div className="ml-auto max-w-2xl rounded-2xl bg-ink px-5 py-3 text-sm text-white">{t.question}</div>
            <div className="card">
              {!t.response && !t.error && <Loading label="Analysing…" />}
              {t.error && <ErrorBox message={t.error} />}
              {t.response && (
                <>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="rounded-full bg-canvas px-2.5 py-0.5 font-semibold capitalize text-muted">{t.response.intent}</span>
                    {t.response.verified
                      ? <span className="rounded-full bg-sage-soft px-2.5 py-0.5 font-semibold text-sage">Verified</span>
                      : <span className="rounded-full bg-rose-soft px-2.5 py-0.5 font-semibold text-rose">Not verified</span>}
                  </div>
                  <p className="mt-3 whitespace-pre-line text-sm leading-relaxed">{t.response.answer}</p>
                  {t.response.limitations.length > 0 && (
                    <ul className="mt-3 list-disc pl-5 text-sm text-muted">
                      {t.response.limitations.map((l) => <li key={l}>{l}</li>)}
                    </ul>
                  )}
                  {t.response.chart && <ChartView chart={t.response.chart} />}
                  {t.response.citations.length > 0 && (
                    <div className="mt-4 border-t border-line pt-3">
                      <div className="label mb-2">Sources</div>
                      <ul className="space-y-1 text-sm">
                        {t.response.citations.map((c) => (
                          <li key={c.chunk_id} className="mono text-muted">
                            {c.filename}{c.page ? `, page ${c.page}` : ""}{c.section ? `, section "${c.section}"` : ""}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {t.response.analysis_results.length > 0 && (
                    <details className="mt-4 text-sm">
                      <summary className="cursor-pointer text-muted">Tool calls ({t.response.analysis_results.length})</summary>
                      <pre className="mono mt-2 max-h-64 overflow-auto rounded-xl bg-canvas p-3">
                        {JSON.stringify(t.response.analysis_results.map((r) => ({ tool: r.tool, args: r.args })), null, 2)}
                      </pre>
                    </details>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      <form onSubmit={onSubmit} className="sticky bottom-4 mt-8 flex gap-3">
        <input
          className="input"
          placeholder="Ask about missing values, averages, outliers, rules or documentation…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={1000}
          disabled={pending}
        />
        <button className="btn-primary" disabled={pending || input.trim().length < 3}>Ask</button>
      </form>
    </>
  );
}
