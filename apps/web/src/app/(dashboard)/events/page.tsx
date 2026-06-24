import { PageHeader } from "@/components/page-header"

export default function EventsPage() {
  return (
    <>
      <PageHeader title="Events" />
      <div className="flex flex-1 flex-col gap-4 p-4">
        <p className="text-muted-foreground text-sm">Event calendar — coming soon.</p>
      </div>
    </>
  )
}
