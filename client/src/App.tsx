import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "@/components/layout/Layout";
import { Home } from "@/pages/Home";
import { Login } from "@/pages/Login";
import { Dashboard } from "@/pages/Dashboard";
import { Missions } from "@/pages/Missions";
import { MissionNew } from "@/pages/MissionNew";
import { MissionDetail } from "@/pages/MissionDetail";
import { Reports } from "@/pages/Reports";
import { Settings } from "@/pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/missions" element={<Missions />} />
          <Route path="/missions/new" element={<MissionNew />} />
          <Route path="/missions/:id" element={<MissionDetail />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
