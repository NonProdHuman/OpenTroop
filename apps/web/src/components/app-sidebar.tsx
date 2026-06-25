"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Calendar, Users, UsersRound, Upload, Settings, Globe } from "lucide-react"
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
  { title: "Members", url: "/members", icon: Users },
  { title: "Groups", url: "/groups", icon: UsersRound },
  { title: "Events", url: "/events", icon: Calendar },
  { title: "Import", url: "/import", icon: Upload },
  { title: "Settings", url: "/settings", icon: Settings },
]

export function AppSidebar() {
  const pathname = usePathname()
  const { data: me } = useMe()
  const isPlatformAdmin = Boolean(me?.platform_role)

  return (
    <Sidebar variant="inset">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-2 py-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground text-xs font-bold select-none">
            OT
          </div>
          <span className="text-base font-semibold tracking-tight">OpenTroop</span>
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
          {isPlatformAdmin ? (
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
          ) : null}
        </SidebarMenu>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <div className="flex items-center gap-3 px-2 py-1">
              <UserButton />
              <span className="text-sm text-sidebar-foreground/70">Account</span>
            </div>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
