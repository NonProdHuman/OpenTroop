/** Page header for the platform console (no sidebar trigger — the console has no sidebar). */
export function ConsoleHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4 md:px-6 bg-background/80 backdrop-blur-sm sticky top-0 z-10">
      <h1 className="text-base font-semibold tracking-tight">{title}</h1>
      {children ? <div className="ml-auto flex items-center gap-2">{children}</div> : null}
    </header>
  )
}
