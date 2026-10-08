import { useState } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Sidebar } from "@/components/layout/Sidebar";
import { Navbar } from "@/components/layout/Navbar";
import { Skeleton } from "@/components/ui/skeleton";

const TITLES: Record<string, string> = {
  "/dashboard": "Operations Dashboard",
  "/missions": "Mission Management",
  "/missions/new": "Create New Mission",
  "/reports": "Reports & Documents",
  "/settings": "Settings",
};

function pageTitle(pathname: string, fallback: string): string {
  if (pathname.startsWith("/missions/") && pathname !== "/missions/new") {
    return "Mission Details";
  }
  return TITLES[pathname] ?? fallback;
}

export function Layout() {
  const { user, loading } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="w-80 space-y-4">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-40 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-screen bg-background">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex min-h-screen flex-col lg:pl-64">
        <Navbar onMenuClick={() => setSidebarOpen(true)} title={pageTitle(location.pathname, "SAR-DSS")} />
        <main className="flex-1 p-4 md:p-6">
          <Outlet />
        </main>
        <footer className="border-t px-6 py-4 text-center text-xs text-muted-foreground">
          SAR-DSS · Airports Authority of India · For operational use only
        </footer>
      </div>
    </div>
  );
}
