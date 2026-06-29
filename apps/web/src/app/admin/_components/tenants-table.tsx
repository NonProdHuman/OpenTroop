import Link from "next/link"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import type { Tenant } from "@/types/api"
import { TenantStatusBadge } from "./tenant-status-badge"

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

export function TenantsTable({
  tenants,
  isLoading = false,
}: {
  tenants: Tenant[]
  isLoading?: boolean
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead><span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Name</span></TableHead>
          <TableHead><span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Slug</span></TableHead>
          <TableHead><span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Status</span></TableHead>
          <TableHead><span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Created</span></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {isLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <TableRow key={i}>
              <TableCell colSpan={4}>
                <Skeleton className="h-5 w-full" />
              </TableCell>
            </TableRow>
          ))
        ) : tenants.length === 0 ? (
          <TableRow>
            <TableCell colSpan={4} className="py-10 text-center text-sm text-muted-foreground">
              No tenants yet. Create the first troop to get started.
            </TableCell>
          </TableRow>
        ) : (
          tenants.map((t) => (
            <TableRow key={t.id} className="hover:bg-muted/40 transition-colors duration-75">
              <TableCell className="font-medium">
                <Link href={`/tenants/${t.id}`} className="hover:underline underline-offset-4">
                  {t.name}
                </Link>
              </TableCell>
              <TableCell className="font-mono text-sm text-muted-foreground">{t.slug}</TableCell>
              <TableCell>
                <TenantStatusBadge tenant={t} />
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {formatDate(t.created_at)}
              </TableCell>
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  )
}
