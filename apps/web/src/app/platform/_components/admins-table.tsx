import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { PlatformAdmin } from "@/types/api"

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
          <TableHead>User</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Role</TableHead>
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
              className="py-8 text-center text-muted-foreground"
            >
              No platform administrators.
            </TableCell>
          </TableRow>
        ) : (
          admins.map((a) => (
            <TableRow key={a.user_id}>
              <TableCell className="font-medium">{a.display_name ?? "—"}</TableCell>
              <TableCell className="text-sm text-muted-foreground">{a.email ?? "—"}</TableCell>
              <TableCell>
                <Badge variant="secondary">{a.platform_role}</Badge>
              </TableCell>
              {canManage ? (
                <TableCell>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive"
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
