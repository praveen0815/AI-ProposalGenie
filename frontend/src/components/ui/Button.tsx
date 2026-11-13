import type { ButtonHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost";

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-cyan-300 text-slate-950 hover:bg-cyan-200 disabled:bg-cyan-300/30 disabled:text-slate-950/50",
  secondary: "border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10 disabled:opacity-50",
  ghost: "text-slate-300 hover:bg-white/5 disabled:opacity-50",
};

export function buttonClasses(variant: ButtonVariant = "primary"): string {
  return [
    "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-semibold transition",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#08111f]",
    "disabled:cursor-not-allowed",
    variantClasses[variant],
  ].join(" ");
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export function Button({ variant = "primary", className = "", type = "button", ...props }: ButtonProps) {
  return <button type={type} className={`${buttonClasses(variant)} ${className}`} {...props} />;
}
