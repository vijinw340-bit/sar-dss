import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, LogOut, Menu, Moon, Search, Sun, User } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { apiGet } from "@/lib/api";
import type { Notification } from "@/types";
import { cn } from "@/lib/utils";

interface NavbarProps {
  onMenuClick: () => void;
  title: string;
}

export function Navbar({ onMenuClick, title }: NavbarProps) {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    apiGet<Notification[]>("/dashboard/notifications")
      .then(setNotifications)
      .catch(() => undefined);
  }, []);

  const criticalCount = notifications.filter((n) => n.level === "critical").length;

  const onSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (search.trim()) navigate(`/missions?search=${encodeURIComponent(search.trim())}`);
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur-lg">
      <Button variant="ghost" size="icon" className="lg:hidden" onClick={onMenuClick}>
        <Menu className="h-5 w-5" />
      </Button>

      <div className="min-w-0">
        <h1 className="truncate text-base font-semibold sm:text-lg">{title}</h1>
        <p className="hidden text-[11px] text-muted-foreground sm:block">
          Search and Rescue Decision Support System · Airports Authority of India
        </p>
      </div>

      <form onSubmit={onSearch} className="relative ml-auto hidden w-64 md:block">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search missions…"
          className="pl-9"
        />
      </form>

      <Button variant="ghost" size="icon" onClick={toggleTheme} title="Toggle theme">
        {theme === "dark" ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" className="relative" title="Notifications">
            <Bell className="h-5 w-5" />
            {criticalCount > 0 && (
              <span className="absolute right-1.5 top-1.5 flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-red-500" />
              </span>
            )}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-80">
          <DropdownMenuLabel>Notifications</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <div className="max-h-72 overflow-y-auto">
            {notifications.map((n, i) => (
              <div
                key={i}
                className={cn(
                  "border-b border-border/50 px-3 py-2 text-xs last:border-0",
                  n.level === "critical" && "bg-red-50 dark:bg-red-950/30"
                )}
              >
                <span
                  className={cn(
                    "mr-2 inline-block h-2 w-2 rounded-full",
                    n.level === "critical" && "bg-red-500",
                    n.level === "warning" && "bg-amber-500",
                    n.level === "info" && "bg-sky-500"
                  )}
                />
                {n.message}
              </div>
            ))}
          </div>
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" title="Account">
            <User className="h-5 w-5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>
            <p className="text-sm font-semibold">{user?.full_name}</p>
            <p className="text-xs font-normal text-muted-foreground">{user?.email}</p>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => navigate("/settings")}>
            <User className="mr-2 h-4 w-4" /> Profile
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => navigate("/reports")}>
            Reports
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="text-red-500 focus:text-red-500" onClick={logout}>
            <LogOut className="mr-2 h-4 w-4" /> Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
