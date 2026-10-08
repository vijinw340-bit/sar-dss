import { NavLink } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Activity,
  ClipboardList,
  LayoutDashboard,
  Plane,
  PlusCircle,
  Settings,
  FileText,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/missions", label: "Missions", icon: ClipboardList },
  { to: "/missions/new", label: "New Mission", icon: PlusCircle },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar({ open, onClose }: SidebarProps) {
  const { user } = useAuth();

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r bg-navy-900 text-white transition-transform duration-300 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-white/10 px-5">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/20">
              <Plane className="h-5 w-5 text-sky-300" />
            </div>
            <div>
              <p className="text-sm font-bold leading-tight">SAR-DSS</p>
              <p className="text-[10px] text-sky-200/70">AAI · Search & Rescue</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" className="text-white lg:hidden" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/20 text-sky-300"
                    : "text-slate-300 hover:bg-white/5 hover:text-white"
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.span
                      layoutId="sidebar-active"
                      className="absolute left-0 top-0 h-full w-1 rounded-r bg-sky-400"
                    />
                  )}
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-white/10 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-sky-400/20 text-xs font-bold text-sky-300">
              {user?.full_name?.charAt(0)?.toUpperCase() ?? "S"}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{user?.full_name ?? "Officer"}</p>
              <p className="flex items-center gap-1 text-[11px] uppercase tracking-wide text-sky-300/80">
                <Activity className="h-3 w-3" />
                {user?.role === "admin" ? "Administrator" : "SAR Officer"}
              </p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
