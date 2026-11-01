import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Loading } from "./components/ui";
import Dashboard from "./pages/Dashboard";

// Pages other than the dashboard are loaded on demand. The Ask page pulls in Recharts,
// so keeping it out of the initial bundle keeps the first load small.
const DatasetOverview = lazy(() => import("./pages/DatasetOverview"));
const DataQuality = lazy(() => import("./pages/DataQuality"));
const Ask = lazy(() => import("./pages/Ask"));
const Documentation = lazy(() => import("./pages/Documentation"));
const Reports = lazy(() => import("./pages/Reports"));

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<Loading label="Loading page…" />}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/datasets/:datasetId" element={<DatasetOverview />} />
            <Route path="/datasets/:datasetId/quality" element={<DataQuality />} />
            <Route path="/datasets/:datasetId/ask" element={<Ask />} />
            <Route path="/datasets/:datasetId/documents" element={<Documentation />} />
            <Route path="/datasets/:datasetId/reports" element={<Reports />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
