import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Triage from "./pages/Triage";
import Vehicle from "./pages/Vehicle";
import Trip from "./pages/Trip";
import Reports from "./pages/Reports";
import Upload from "./pages/Upload";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="triage" element={<Triage />} />
          <Route path="vehicle/:vehicle_id" element={<Vehicle />} />
          <Route path="trip/:trip_id" element={<Trip />} />
          <Route path="reports" element={<Reports />} />
          <Route path="upload" element={<Upload />} />
          <Route path="*" element={<div className="text-slate-500">Pagina nao encontrada</div>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
