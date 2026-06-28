"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  UserRound,
  CalendarDays,
  ChevronRight,
  MessageSquare,
  Star,
  BarChart3,
  Settings2,
  Globe,
  type LucideIcon,
} from "lucide-react"
import { UserButton } from "@clerk/nextjs"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  useSidebar,
} from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"
import { useMe } from "@/hooks/use-me"
import { usePermissions } from "@/hooks/use-session"
import { TenantSwitcher } from "@/components/tenant-switcher"
import type { Permission } from "@/types/api"

/**
 * Navigation registry. The sidebar follows the hybrid IA model
 * (docs/spec/navigation.md): top-level entries are **destinations** (leaf links)
 * or **collapsible groups** whose children are destinations. In-page tabs (e.g.
 * the Events list/calendar toggle) handle "lenses on the same data" separately.
 */
type NavChild = { title: string; url: string; requires?: Permission; disabledMessage?: string }
type NavItem = {
  title: string
  icon: LucideIcon
  /** Leaf link target. Omitted for pure groups (which only expand/collapse). */
  url?: string
  requires?: Permission
  platformAdminOnly?: boolean
  disabledMessage?: string
  children?: NavChild[]
}

const navItems: NavItem[] = [
  {
    title: "Membership",
    icon: UserRound,
    children: [
      { title: "Members", url: "/members", requires: "member:read" },
      { title: "Groups", url: "/groups", requires: "member:read" },
      { title: "Positions", url: "/positions", requires: "role:manage" },
      { title: "Functional Roles", url: "/functional-roles", requires: "role:manage" },
    ],
  },
  { title: "Events", url: "/events", icon: CalendarDays, requires: "event:read" },
  { title: "Messaging", icon: MessageSquare, disabledMessage: "Coming soon" },
  { title: "Advancement", icon: Star, disabledMessage: "Coming soon" },
  { title: "Reports", icon: BarChart3, disabledMessage: "Coming soon" },
  {
    title: "Admin",
    icon: Settings2,
    children: [
      { title: "Settings", url: "/settings", requires: "role:manage" },
      { title: "Import", url: "/import", requires: "member:write" },
    ],
  },
  {
    title: "Platform",
    icon: Globe,
    platformAdminOnly: true,
    children: [
      { title: "Tenants", url: "/platform/tenants" },
      { title: "Admins", url: "/platform/admins" },
    ],
  },
]

export function AppSidebar() {
  const pathname = usePathname()
  const { data: me } = useMe()
  const isPlatformAdmin = Boolean(me?.platform_role)
  const { has } = usePermissions()
  const { state, setOpen } = useSidebar()

  const isActive = (url: string) => pathname === url || pathname.startsWith(url + "/")
  const groupActive = (item: NavItem) => item.children?.some((c) => isActive(c.url)) ?? false

  // Track which groups the user has toggled. A group defaults to open when it
  // contains the active route, so the active section is always revealed.
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({})
  const isOpen = (item: NavItem) => openGroups[item.title] ?? groupActive(item)

  const [autoExpanded, setAutoExpanded] = useState(false)

  if (state === "collapsed" && autoExpanded) {
    setAutoExpanded(false)
  }

  const toggle = (item: NavItem) => {
    if (state === "collapsed") {
      setOpen(true)
      setAutoExpanded(true)
      setOpenGroups((prev) => ({ ...prev, [item.title]: true }))
    } else {
      setAutoExpanded(false)
      setOpenGroups((prev) => ({ ...prev, [item.title]: !isOpen(item) }))
    }
  }

  const handleNavClick = () => {
    if (autoExpanded) {
      setOpen(false)
      setAutoExpanded(false)
    }
  }

  return (
    <Sidebar collapsible="icon" variant="sidebar">
      <SidebarHeader>
        <div className="flex items-center gap-2.5 px-2 py-1">
          {/* Logo mark */}
          <div
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-bold select-none"
            style={{ background: "var(--sidebar-primary)", color: "var(--sidebar-primary-foreground)" }}
          >
            OT
          </div>
          <span className="text-base font-semibold tracking-tight" style={{ color: "var(--sidebar-foreground)" }}>
            OpenTroop
          </span>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarMenu>
          {navItems.map((item) => {
            if (item.platformAdminOnly && !isPlatformAdmin) return null

            const hasAccess = !item.requires || has(item.requires)
            const isDisabled = Boolean(item.disabledMessage) || !hasAccess
            const tooltip = item.disabledMessage
              ? `${item.title} — ${item.disabledMessage}`
              : !hasAccess ? `${item.title} — Access denied` : item.title

            if (item.children) {
              return (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton
                    onClick={() => toggle(item)}
                    isActive={groupActive(item)}
                    aria-expanded={isOpen(item)}
                    tooltip={tooltip}
                    className={isDisabled ? "opacity-50" : ""}
                  >
                    <item.icon />
                    <span>{item.title}</span>
                    <ChevronRight
                      className={cn("ml-auto transition-transform", isOpen(item) && "rotate-90")}
                    />
                  </SidebarMenuButton>
                  {isOpen(item) ? (
                    <SidebarMenuSub>
                      {item.children.map((child) => {
                        const childHasAccess = !child.requires || has(child.requires)
                        const childIsDisabled = Boolean(child.disabledMessage) || !childHasAccess
                        return (
                          <SidebarMenuSubItem key={child.title}>
                            <SidebarMenuSubButton
                              render={childIsDisabled ? <span /> : <Link href={child.url} />}
                              isActive={isActive(child.url)}
                              className={childIsDisabled ? "opacity-50 cursor-not-allowed" : ""}
                              onClick={childIsDisabled ? undefined : handleNavClick}
                            >
                              <span>{child.title}</span>
                            </SidebarMenuSubButton>
                          </SidebarMenuSubItem>
                        )
                      })}
                    </SidebarMenuSub>
                  ) : null}
                </SidebarMenuItem>
              )
            }

            return (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  render={isDisabled ? <span /> : <Link href={item.url!} />}
                  isActive={isActive(item.url!)}
                  tooltip={tooltip}
                  className={isDisabled ? "opacity-50 cursor-not-allowed" : ""}
                  onClick={isDisabled ? undefined : handleNavClick}
                >
                  <item.icon />
                  <span>{item.title}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )
          })}
        </SidebarMenu>
      </SidebarContent>

      <SidebarFooter>
        <TenantSwitcher />
        <SidebarMenu>
          <SidebarMenuItem>
            <div className="flex items-center gap-3 px-2 py-1">
              <UserButton />
              <span className="text-sm" style={{ color: "var(--sidebar-foreground)", opacity: 0.6 }}>
                Account
              </span>
            </div>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
