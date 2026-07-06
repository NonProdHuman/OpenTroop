import { redirect } from "next/navigation"

// /advancement is a group of sub-pages (Scouts, Approval queue, later reports);
// the bare path lands on the viewer.
export default function AdvancementIndexPage() {
  redirect("/advancement/scouts")
}
