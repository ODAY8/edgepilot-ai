import { motion } from "framer-motion";
import { Maximize2, Radio } from "lucide-react";
import { useEffect, useState } from "react";

interface CameraPanelProps {
  cameraId?: string;
  edgeNode?: string;
  hasDetection?: boolean;
}

export default function CameraPanel({
  cameraId = "CAM-01",
  edgeNode = "EDGE NODE 01",
  hasDetection = true,
}: CameraPanelProps) {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const timestamp = now.toLocaleTimeString("en-US", { hour12: false });

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-2xl border border-border bg-[#05060a]">
      {/* Base video-like surface */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_20%,rgba(91,124,250,0.14),transparent_55%),radial-gradient(ellipse_at_75%_75%,rgba(139,107,245,0.10),transparent_50%)]" />
      <div className="absolute inset-0 bg-grid opacity-40" />

      {/* Scanline sweep */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute inset-x-0 h-24 animate-scan bg-linear-to-b from-transparent via-accent/10 to-transparent" />
      </div>

      {/* Mock industrial silhouette shapes for realism */}
      <svg className="absolute inset-0 h-full w-full opacity-[0.15]" preserveAspectRatio="none" viewBox="0 0 400 225">
        <rect x="20" y="150" width="60" height="60" fill="white" />
        <rect x="100" y="120" width="40" height="90" fill="white" />
        <rect x="300" y="100" width="80" height="110" fill="white" />
        <line x1="0" y1="140" x2="400" y2="140" stroke="white" strokeWidth="1" />
      </svg>

      {/* Detection bounding box */}
      {hasDetection && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="absolute left-[38%] top-[32%] h-[38%] w-[20%] rounded-sm border-2 border-critical/80 shadow-[0_0_16px_rgba(248,85,90,0.5)]"
        >
          <span className="absolute -top-6 left-0 rounded bg-critical/90 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">
            Person · 94%
          </span>
        </motion.div>
      )}

      {/* Top overlay row */}
      <div className="absolute inset-x-0 top-0 flex items-start justify-between p-4">
        <div className="flex items-center gap-2 rounded-md bg-black/50 px-2.5 py-1.5 backdrop-blur-sm">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-pulse-slow rounded-full bg-critical opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-critical" />
          </span>
          <span className="text-[11px] font-bold uppercase tracking-widest text-white">Live</span>
        </div>
        <div className="flex items-center gap-2 rounded-md bg-black/50 px-2.5 py-1.5 backdrop-blur-sm">
          <Radio size={12} className="text-accent" />
          <span className="font-mono text-[11px] text-white/80">{edgeNode}</span>
        </div>
      </div>

      {/* Bottom overlay row */}
      <div className="absolute inset-x-0 bottom-0 flex items-end justify-between p-4">
        <div className="rounded-md bg-black/50 px-2.5 py-1.5 backdrop-blur-sm">
          <p className="font-mono text-[11px] font-semibold text-white">{cameraId}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="rounded-md bg-black/50 px-2.5 py-1.5 backdrop-blur-sm">
            <p className="font-mono text-[11px] text-white/70">{timestamp}</p>
          </div>
          <button
            aria-label="Expand camera view"
            className="rounded-md bg-black/50 p-1.5 text-white/70 backdrop-blur-sm transition-colors hover:text-white"
          >
            <Maximize2 size={13} />
          </button>
        </div>
      </div>
    </div>
  );
}
