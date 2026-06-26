"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  UserRound,
  Shield,
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
} from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"
import { useMe } from "@/hooks/use-me"
import { usePermissions } from "@/hooks/use-session"
import type { Permission } from "@/types/api"

/**
 * Navigation registry. The sidebar follows the hybrid IA model
 * (docs/spec/navigation.md): top-level entries are **destinations** (leaf links)
 * or **collapsible groups** whose children are destinations. In-page tabs (e.g.
 * the Events list/calendar toggle) handle "lenses on the same data" separately.
 */
type NavChild = { title: string; url: string; requires?: Permission }
type NavItem = {
  title: string
  icon: LucideIcon
  /** Leaf link target. Omitted for pure groups (which only expand/collapse). */
  url?: string
  requires?: Permission
  children?: NavChild[]
}

const navItems: NavItem[] = [
  { title: "Members", url: "/members", icon: UserRound, requires: "member:read" },
  { title: "Groups", url: "/groups", icon: Shield, requires: "member:read" },
  { title: "Events", url: "/events", icon: CalendarDays, requires: "event:read" },
  {
    title: "Admin",
    icon: Settings2,
    children: [
      { title: "Settings", url: "/settings", requires: "role:manage" },
      { title: "Import", url: "/import", requires: "member:write" },
    ],
  },
]

/** Future nav items — shown grayed-out to communicate roadmap */
const futureNavItems = [
  { title: "Messaging", icon: MessageSquare, label: "Coming soon" },
  { title: "Advancement", icon: Star, label: "Coming soon" },
  { title: "Reports", icon: BarChart3, label: "Coming soon" },
]

export function AppSidebar() {
  const pathname = usePathname()
  const { data: me } = useMe()
  const isPlatformAdmin = Boolean(me?.platform_role)
  const { has } = usePermissions()

  const isActive = (url: string) => pathname === url || pathname.startsWith(url + "/")
  const groupActive = (item: NavItem) => item.children?.some((c) => isActive(c.url)) ?? false

  // Track which groups the user has toggled. A group defaults to open when it
  // contains the active route, so the active section is always revealed.
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({})
  const isOpen = (item: NavItem) => openGroups[item.title] ?? groupActive(item)
  const toggle = (item: NavItem) =>
    setOpenGroups((prev) => ({ ...prev, [item.title]: !isOpen(item) }))

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
            if (item.requires && !has(item.requires)) return null
            const visibleChildren = item.children?.filter(
              (c) => !c.requires || has(c.requires),
            )
            if (item.children && visibleChildren?.length === 0) return null
            return item.children ? (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  onClick={() => toggle(item)}
                  isActive={groupActive(item)}
                  aria-expanded={isOpen(item)}
                  tooltip={item.title}
                >
                  <item.icon />
                  <span>{item.title}</span>
                  <ChevronRight
                    className={cn("ml-auto transition-transform", isOpen(item) && "rotate-90")}
                  />
                </SidebarMenuButton>
                {isOpen(item) ? (
                  <SidebarMenuSub>
                    {visibleChildren!.map((child) => (
                      <SidebarMenuSubItem key={child.title}>
                        <SidebarMenuSubButton
                          render={<Link href={child.url} />}
                          isActive={isActive(child.url)}
                        >
                          <span>{child.title}</span>
                        </SidebarMenuSubButton>
                      </SidebarMenuSubItem>
                    ))}
                  </SidebarMenuSub>
                ) : null}
              </SidebarMenuItem>
            ) : (
              <SidebarMenuItem key={item.title}>
                <SidebarMenuButton
                  render={<Link href={item.url!} />}
                  isActive={isActive(item.url!)}
                  tooltip={item.title}
                >
                  <item.icon />
                  <span>{item.title}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            )
          })}

          {isPlatformAdmin && (
            <SidebarMenuItem>
              <SidebarMenuButton
                render={<Link href="/platform" />}
                isActive={pathname.startsWith("/platform")}
                tooltip="Platform console"
              >
                <Globe />
                <span>Platform</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          )}

          {/* Future nav items — disabled/grayed to show roadmap */}
          {futureNavItems.map((item) => (
            <SidebarMenuItem key={item.title}>
              <SidebarMenuButton
                disabled
                tooltip={`${item.title} — ${item.label}`}
                className="opacity-40 cursor-not-allowed"
              >
                <item.icon />
                <span>{item.title}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}
        </SidebarMenu>
      </SidebarContent>

      <SidebarFooter>
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
