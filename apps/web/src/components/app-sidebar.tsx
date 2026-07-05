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
import { ThemeToggle } from "@/components/theme-toggle"
import { getAdminUrl } from "@/lib/domains"
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

const tenantNavItems: NavItem[] = [
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
  {
    title: "Messaging",
    icon: MessageSquare,
    children: [
      // Inbox for every member; Announcements only for senders.
      { title: "Inbox", url: "/messages/inbox" },
      { title: "Announcements", url: "/messages", requires: "communication:send_troop" },
    ],
  },
  {
    title: "Advancement",
    icon: Star,
    children: [
      // No `requires`: scouts and parents see their own family's advancement —
      // the backend scopes the picker (GH-191).
      { title: "Scouts", url: "/advancement/scouts" },
      { title: "Approval Queue", url: "/advancement/queue", requires: "advancement:approve" },
    ],
  },
  { title: "Reports", icon: BarChart3, disabledMessage: "Coming soon" },
  {
    title: "Admin",
    icon: Settings2,
    children: [
      { title: "Settings", url: "/settings", requires: "role:manage" },
      { title: "Import", url: "/import", requires: "member:write" },
    ],
  },
]

const adminNavItems: NavItem[] = [
  { title: "Tenants", url: "/tenants", icon: Globe },
  { title: "Admins", url: "/admins", icon: UserRound },
]

export function AppSidebar({ isAdminView = false }: { isAdminView?: boolean }) {
  const pathname = usePathname()
  const { data: me } = useMe()
  const isPlatformAdmin = Boolean(me?.platform_role)
  // In admin view the console is platform-scoped (gated by platform_role), so don't
  // fetch tenant RBAC — avoids a spurious tenant-scoped /auth/session on admin hosts.
  const { has } = usePermissions(!isAdminView)
  const { state, setOpen } = useSidebar()
  const currentNavItems = isAdminView ? adminNavItems : tenantNavItems

  const isActive = (url: string) => pathname === url || pathname.startsWith(url + "/")
  const groupActive = (item: NavItem) => {
    const visibleChildren = item.children?.filter((c) => !c.requires || has(c.requires)) ?? []
    return visibleChildren.some((c) => isActive(c.url))
  }

  // Track which group is open. Only one group can be open at a time.
  const [openGroup, setOpenGroup] = useState<string | null>(null)
  const [lastPathname, setLastPathname] = useState<string | null>(null)

  const activeGroupItem = currentNavItems.find((item) => groupActive(item))
  const activeGroupTitle = activeGroupItem ? activeGroupItem.title : null

  // If the pathname has changed, reset the openGroup to the active group.
  if (pathname !== lastPathname) {
    setLastPathname(pathname)
    setOpenGroup(activeGroupTitle)
  }

  const isOpen = (item: NavItem) => {
    if (openGroup !== null) {
      return item.title === openGroup
    }
    return groupActive(item)
  }

  const [autoExpanded, setAutoExpanded] = useState(false)

  if (state === "collapsed" && autoExpanded) {
    setAutoExpanded(false)
  }

  const toggle = (item: NavItem) => {
    if (state === "collapsed") {
      setOpen(true)
      setAutoExpanded(true)
      setOpenGroup(item.title)
    } else {
      setAutoExpanded(false)
      setOpenGroup((prev) => (prev === item.title ? "" : item.title))
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
          {currentNavItems.map((item) => {
            if (item.platformAdminOnly && !isPlatformAdmin) return null

            const hasAccess = !item.requires || has(item.requires)
            if (!hasAccess) return null

            const isDisabled = Boolean(item.disabledMessage)
            const tooltip = item.disabledMessage
              ? `${item.title} — ${item.disabledMessage}`
              : item.title

            if (item.children) {
              const visibleChildren = item.children.filter((child) => !child.requires || has(child.requires))
              if (visibleChildren.length === 0) return null

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
                      {visibleChildren.map((child) => {
                        const childIsDisabled = Boolean(child.disabledMessage)
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
        {!isAdminView && isPlatformAdmin && (
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton render={<Link href={getAdminUrl("/tenants")} />}>
                <Globe />
                <span>Platform Admin</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        )}
        <TenantSwitcher />
        <ThemeToggle />
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
