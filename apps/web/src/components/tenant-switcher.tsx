"use client"

import { useEffect } from "react"
import Link from "next/link"
import { Building2, ChevronsUpDown, Check } from "lucide-react"
import { useMemberships } from "@/hooks/use-memberships"
import { useActiveTenant } from "@/lib/tenant-context"
import { getTenantRedirectUrl } from "@/lib/subdomain"
import { getTenantUrl } from "@/lib/domains"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"

export function TenantSwitcher() {
  const { data: memberships = [], isLoading } = useMemberships()
  const { activeTenantId, setActiveTenantId } = useActiveTenant()

  // Auto-select the first membership when no tenant is active.
  useEffect(() => {
    if (!isLoading && memberships.length > 0 && !activeTenantId) {
      setActiveTenantId(memberships[0].tenant_id)
    }
  }, [isLoading, memberships, activeTenantId, setActiveTenantId])

  const activeMembership = memberships.find((m) => m.tenant_id === activeTenantId)

  // Single membership — no dropdown, but make it a link to the troop's dashboard so
  // it works as navigation (notably from the admin console back into the tenant).
  if (memberships.length <= 1) {
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          {activeMembership ? (
            <SidebarMenuButton render={<Link href={getTenantUrl(activeMembership.tenant_slug, "/members")} />}>
              <Building2 className="h-4 w-4 shrink-0 opacity-50" />
              <span className="text-sm font-medium truncate">
                {activeMembership.tenant_name}
              </span>
            </SidebarMenuButton>
          ) : (
            <div className="flex items-center gap-2 px-2 py-1">
              <Building2 className="h-4 w-4 shrink-0" style={{ color: "var(--sidebar-foreground)", opacity: 0.5 }} />
              <span
                className="text-sm font-medium truncate"
                style={{ color: "var(--sidebar-foreground)" }}
              >
                No troop selected
              </span>
            </div>
          )}
        </SidebarMenuItem>
      </SidebarMenu>
    )
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton
                size="lg"
                className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
              />
            }
          >
            <Building2 className="h-4 w-4 shrink-0" />
            <div className="grid flex-1 text-left text-sm leading-tight">
              <span className="truncate font-semibold">
                {activeMembership?.tenant_name ?? "Select troop"}
              </span>
            </div>
            <ChevronsUpDown className="ml-auto h-4 w-4 shrink-0 opacity-50" />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
            align="start"
            side="top"
            sideOffset={4}
          >
            {memberships.map((m) => (
              <DropdownMenuItem
                key={m.tenant_id}
                onClick={() => {
                  const redirectUrl = getTenantRedirectUrl(m.tenant_slug, "/members")
                  if (redirectUrl) {
                    window.location.href = redirectUrl
                  } else {
                    setActiveTenantId(m.tenant_id)
                  }
                }}
                className="gap-2"
              >
                <Building2 className="h-4 w-4 shrink-0 opacity-50" />
                <span className="flex-1">{m.tenant_name}</span>
                {m.tenant_id === activeTenantId && (
                  <Check className="h-4 w-4 shrink-0" />
                )}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
