/** Page header for the platform console (no sidebar trigger — the console has no sidebar). */
export function ConsoleHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4 md:px-6">
      <h1 className="text-sm font-semibold">{title}</h1>
      {children ? <div className="ml-auto flex items-center gap-2">{children}</div> : null}
    </header>
  )
}
