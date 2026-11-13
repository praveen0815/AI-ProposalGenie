interface SpinnerProps {
  label: string;
}

export function Spinner({ label }: SpinnerProps) {
  return (
    <div
      role="status"
      className="flex items-center gap-3 rounded-2xl border border-white/10 bg-[#101c31] px-5 py-8 text-sm text-slate-300"
    >
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-300/30 border-t-cyan-300" />
      {label}
    </div>
  );
}
