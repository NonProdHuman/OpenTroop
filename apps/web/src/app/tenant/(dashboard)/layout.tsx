import { AppSidebar } from "@/components/app-sidebar"
import { DemoBanner } from "@/components/demo-banner"
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <DemoBanner />
        {children}
      </SidebarInset>
    </SidebarProvider>
  )
}
