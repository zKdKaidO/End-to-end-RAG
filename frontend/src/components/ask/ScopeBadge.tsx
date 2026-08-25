export function ScopeBadge({ label, onClick }: { label: string; onClick: () => void }) {
  return <button className="rounded-full border-0 bg-blue-50 px-2.5 py-1 text-[10px] font-semibold text-blue-700 hover:bg-blue-100" onClick={onClick}>Active Scope · {label}</button>;
}
