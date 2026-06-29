import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { PlatformAdmin } from "@/types/api"

const ROLE_BADGE: Record<string, string> = {
  superadmin: "bg-amber-50 text-amber-700 border border-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-900",
  support:    "bg-slate-100 text-slate-700 border border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
  billing:    "bg-purple-50 text-purple-700 border border-purple-200 dark:bg-purple-950 dark:text-purple-300 dark:border-purple-900",
}

export function AdminsTable({
  admins,
  isLoading = false,
  canManage = false,
  onRevoke,
}: {
  admins: PlatformAdmin[]
  isLoading?: boolean
  canManage?: boolean
  onRevoke?: (admin: PlatformAdmin) => void
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead><span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">User</span></TableHead>
          <TableHead><span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Email</span></TableHead>
          <TableHead><span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Role</span></TableHead>
          {canManage ? <TableHead className="w-0" /> : null}
        </TableRow>
      </TableHeader>
      <TableBody>
        {isLoading ? (
          <TableRow>
            <TableCell colSpan={canManage ? 4 : 3}>
              <Skeleton className="h-5 w-full" />
            </TableCell>
          </TableRow>
        ) : admins.length === 0 ? (
          <TableRow>
            <TableCell
              colSpan={canManage ? 4 : 3}
              className="py-10 text-center text-sm text-muted-foreground"
            >
              No platform administrators.
            </TableCell>
          </TableRow>
        ) : (
          admins.map((a) => (
            <TableRow key={a.user_id} className="hover:bg-muted/40 transition-colors duration-75">
              <TableCell className="font-medium">{a.display_name ?? "—"}</TableCell>
              <TableCell className="text-sm text-muted-foreground">{a.email ?? "—"}</TableCell>
              <TableCell>
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${ROLE_BADGE[a.platform_role] ?? ROLE_BADGE.support}`}
                >
                  {a.platform_role}
                </span>
              </TableCell>
              {canManage ? (
                <TableCell>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive hover:text-destructive"
                    onClick={() => onRevoke?.(a)}
                  >
                    Revoke
                  </Button>
                </TableCell>
              ) : null}
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  )
}
