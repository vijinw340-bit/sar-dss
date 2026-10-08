import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Moon, Shield, Sun, User as UserIcon } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { apiError, apiGet, apiPatch } from "@/lib/api";
import type { User } from "@/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

export function Settings() {
  const { user } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [users, setUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [error, setError] = useState("");

  const isAdmin = user?.role === "admin";

  useEffect(() => {
    if (isAdmin) {
      setLoadingUsers(true);
      apiGet<User[]>("/users")
        .then(setUsers)
        .catch((e) => setError(apiError(e)))
        .finally(() => setLoadingUsers(false));
    }
  }, [isAdmin]);

  const updateUser = async (id: number, patch: Partial<User>) => {
    try {
      const updated = await apiPatch<User>(`/users/${id}`, patch);
      setUsers((prev) => prev.map((u) => (u.id === id ? updated : u)));
      setError("");
    } catch (e) {
      setError(apiError(e));
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h2 className="text-xl font-bold text-navy-900 dark:text-white">Settings</h2>
        <p className="text-sm text-muted-foreground">Account, appearance and user administration</p>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="glass">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UserIcon className="h-4 w-4 text-primary" /> Profile
              </CardTitle>
              <CardDescription>Your account information</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg bg-muted/50 p-3">
                  <p className="text-xs text-muted-foreground">Full name</p>
                  <p className="font-medium">{user?.full_name}</p>
                </div>
                <div className="rounded-lg bg-muted/50 p-3">
                  <p className="text-xs text-muted-foreground">Username</p>
                  <p className="font-medium">{user?.username}</p>
                </div>
                <div className="rounded-lg bg-muted/50 p-3">
                  <p className="text-xs text-muted-foreground">Email</p>
                  <p className="truncate font-medium">{user?.email}</p>
                </div>
                <div className="rounded-lg bg-muted/50 p-3">
                  <p className="text-xs text-muted-foreground">Designation</p>
                  <p className="font-medium">{user?.designation ?? "SAR Officer"}</p>
                </div>
              </div>
              <Badge variant="outline" className="gap-1.5">
                <Shield className="h-3 w-3 text-primary" />
                {user?.role === "admin" ? "Administrator" : "SAR Officer"} role
              </Badge>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
          <Card className="glass">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {theme === "dark" ? <Moon className="h-4 w-4 text-primary" /> : <Sun className="h-4 w-4 text-primary" />}
                Appearance
              </CardTitle>
              <CardDescription>Toggle between light and dark aviation theme</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between rounded-lg bg-muted/50 p-4">
                <div>
                  <p className="text-sm font-medium">Dark mode</p>
                  <p className="text-xs text-muted-foreground">Night-operations friendly interface</p>
                </div>
                <Switch checked={theme === "dark"} onCheckedChange={toggleTheme} />
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {isAdmin && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <Card className="glass">
            <CardHeader>
              <CardTitle>User Management</CardTitle>
              <CardDescription>Manage officer accounts and roles (admin only)</CardDescription>
            </CardHeader>
            <CardContent>
              {loadingUsers ? (
                <Skeleton className="h-40 w-full rounded-xl" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead className="hidden md:table-cell">Email</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead>Active</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((u) => (
                      <TableRow key={u.id}>
                        <TableCell>
                          <p className="font-medium">{u.full_name}</p>
                          <p className="text-xs text-muted-foreground">@{u.username}</p>
                        </TableCell>
                        <TableCell className="hidden md:table-cell">{u.email}</TableCell>
                        <TableCell>
                          <Select
                            value={u.role}
                            disabled={u.id === user?.id}
                            onValueChange={(v) => updateUser(u.id, { role: v as User["role"] })}
                          >
                            <SelectTrigger className="h-8 w-36">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="sar_officer">SAR Officer</SelectItem>
                              <SelectItem value="admin">Admin</SelectItem>
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <Switch
                            checked={u.is_active}
                            disabled={u.id === user?.id}
                            onCheckedChange={(v) => updateUser(u.id, { is_active: v })}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}

      <Card className="glass">
        <CardHeader>
          <CardTitle>About</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p><strong className="text-foreground">SAR-DSS</strong> — Search and Rescue Decision Support System.</p>
          <p>Developed for the Airports Authority of India to compute and plot the probable search area of a missing aircraft from its last known position.</p>
          <p className="text-xs">API base: {import.meta.env.VITE_API_URL || "/api/v1"} · Version 1.0.0</p>
        </CardContent>
      </Card>
    </div>
  );
}
