interface SkeletonProps {
  className?: string;
}

// A single pulsing placeholder block -- deliberately generic (just a
// sized, rounded surface) so callers compose it into whatever shape a
// loading section needs, instead of one skeleton component per page.
export default function Skeleton({ className = "" }: SkeletonProps) {
  return <div className={`animate-pulse rounded-lg bg-surface-2 ${className}`} />;
}
