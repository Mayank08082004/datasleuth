import { useEffect, useState } from "react";
import { NavLink, Outlet, useParams } from "react-router-dom";
import { getApiKey, setApiKey } from "../api";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-xl px-3 py-2 text-sm font-semibold transition ${
    isActive ? "bg-amber text-ink" : "text-muted hover:bg-white hover:text-ink"
  }`;

export default function Layout() {
  const { datasetId } = useParams();
  const [key, setKey] = useState(getApiKey());
  const [saved, setSaved] = useState(false);

  useEffect(() => setSaved(false), [key]);

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="w-full shrink-0 border-b border-line bg-canvas px-4 py-4 md:w-60 md:border-b-0 md:border-r md:py-6">
        <div className="mb-8 px-3">
          <div className="font-serif text-2xl font-bold">DataSleuth</div>
          <div className="text-xs text-muted">Dataset exploration &amp; quality audit</div>
        </div>
        <nav className="flex flex-wrap gap-1 md:block md:space-y-1">
          <NavLink to="/" end className={navClass}>Dashboard</NavLink>
          {datasetId && (
            <>
              <div className="label mt-6 px-3 pb-1">Current dataset</div>
              <NavLink to={`/datasets/${datasetId}`} end className={navClass}>Overview</NavLink>
              <NavLink to={`/datasets/${datasetId}/quality`} className={navClass}>Data quality</NavLink>
              <NavLink to={`/datasets/${datasetId}/ask`} className={navClass}>Ask DataSleuth</NavLink>
              <NavLink to={`/datasets/${datasetId}/documents`} className={navClass}>Documentation</NavLink>
              <NavLink to={`/datasets/${datasetId}/reports`} className={navClass}>Reports</NavLink>
            </>
          )}
        </nav>
        <div className="mt-6 border-t border-line pt-4 px-3 md:mt-10">
          <label className="label" htmlFor="apikey">API key</label>
          <input
            id="apikey"
            type="password"
            className="input mt-1"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="DATASLEUTH_API_KEY"
          />
          <button
            className="btn-ghost mt-2 w-full"
            onClick={() => {
              setApiKey(key);
              setSaved(true);
            }}
          >
            {saved ? "Saved" : "Save key"}
          </button>
          <p className="mt-2 text-xs text-muted">Stored in this browser only.</p>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-4 py-6 md:px-10 md:py-8 max-w-6xl">
        <Outlet />
      </main>
    </div>
  );
}
