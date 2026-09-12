import { motion } from "framer-motion";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

type NativeButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  "onDrag" | "onDragStart" | "onDragEnd" | "onAnimationStart" | "onAnimationEnd" | "onAnimationIteration"
>;

interface ButtonProps extends NativeButtonProps {
  variant?: Variant;
  icon?: ReactNode;
  children: ReactNode;
}

const VARIANT_STYLES: Record<Variant, string> = {
  primary:
    "bg-linear-to-r from-accent to-accent-2 text-white shadow-[0_0_0_1px_rgba(91,124,250,0.4),0_8px_24px_-8px_rgba(91,124,250,0.6)] hover:brightness-110",
  secondary:
    "bg-surface-3 text-ink border border-border hover:border-accent/50 hover:bg-surface-3/80",
  danger:
    "bg-critical/10 text-critical border border-critical/30 hover:bg-critical/20",
  ghost: "text-ink-dim hover:text-ink hover:bg-surface-2",
};

export default function Button({
  variant = "primary",
  icon,
  children,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <motion.button
      whileTap={{ scale: 0.97 }}
      whileHover={{ scale: 1.015 }}
      transition={{ duration: 0.12 }}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT_STYLES[variant]} ${className}`}
      {...props}
    >
      {icon}
      {children}
    </motion.button>
  );
}
