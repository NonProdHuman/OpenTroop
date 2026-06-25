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
          <TableHead>Name</TableHead>
          <TableHead>Slug</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Created</TableHead>
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
            <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
              No tenants yet. Create the first troop to get started.
            </TableCell>
          </TableRow>
        ) : (
          tenants.map((t) => (
            <TableRow key={t.id}>
              <TableCell className="font-medium">
                <Link href={`/platform/tenants/${t.id}`} className="hover:underline">
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
