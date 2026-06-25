"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  UserRound,
  Shield,
  CalendarDays,
  MessageSquare,
  Star,
  FolderInput,
  BarChart3,
  Settings2,
  Globe,
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
} from "@/components/ui/sidebar"
import { useMe } from "@/hooks/use-me"

const navItems = [
  { title: "Members",  url: "/members",  icon: UserRound   },
  { title: "Groups",   url: "/groups",   icon: Shield      },
  { title: "Events",   url: "/events",   icon: CalendarDays },
  { title: "Import",   url: "/import",   icon: FolderInput },
  { title: "Settings", url: "/settings", icon: Settings2   },
]

/** Future nav items — shown grayed-out to communicate roadmap */
const futureNavItems = [
  { title: "Messaging",    icon: MessageSquare, label: "Coming soon" },
  { title: "Advancement",  icon: Star,          label: "Coming soon" },
  { title: "Reports",      icon: BarChart3,     label: "Coming soon" },
]

export function AppSidebar() {
  const pathname = usePathname()
  const { data: me } = useMe()
  const isPlatformAdmin = Boolean(me?.platform_role)

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
          {navItems.map((item) => (
            <SidebarMenuItem key={item.title}>
              <SidebarMenuButton
                render={<Link href={item.url} />}
                isActive={pathname === item.url || pathname.startsWith(item.url + "/")}
                tooltip={item.title}
              >
                <item.icon />
                <span>{item.title}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          ))}

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
