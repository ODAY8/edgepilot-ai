import { motion } from "framer-motion";
import { AlertTriangle, Camera, Loader2, Radio, ShieldAlert, Video, VideoOff } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import Button from "@/components/common/Button";
import { analyzeFrame, type LiveFrameResult } from "@/services/api";

type CameraStatus = "idle" | "requesting" | "live" | "denied" | "unavailable";

const CAPTURE_INTERVAL_MS = 4000;
const LIVE_CAMERA_ID = "CAM-LIVE-01";

interface CameraPanelProps {
  cameraId?: string;
  edgeNode?: string;
  location?: string;
  onIncidentCreated?: (incidentId: string) => void;
}

export default function CameraPanel({
  cameraId = LIVE_CAMERA_ID,
  edgeNode = "BROWSER EDGE NODE",
  location,
  onIncidentCreated,
}: CameraPanelProps) {
  const [status, setStatus] = useState<CameraStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [now, setNow] = useState(new Date());
  const [lastResult, setLastResult] = useState<LiveFrameResult | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isAnalyzingRef = useRef(false);

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const stopCamera = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    isAnalyzingRef.current = false;
    setStatus("idle");
    setLastResult(null);
  }, []);

  // Never leave the webcam LED on if the operator navigates away.
  useEffect(() => stopCamera, [stopCamera]);

  const captureAndAnalyze = useCallback(() => {
    if (isAnalyzingRef.current) return; // previous request still in flight -- skip this tick
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      async (blob) => {
        if (!blob) return;
        isAnalyzingRef.current = true;
        try {
          const result = await analyzeFrame(blob, cameraId, location);
          setLastResult(result);
          if (result.incidentCreated && result.incidentId) {
            onIncidentCreated?.(result.incidentId);
          }
        } catch {
          // A single failed frame (e.g. a transient network hiccup or the
          // backend briefly unreachable) shouldn't stop live monitoring --
          // the next capture tick just tries again.
        } finally {
          isAnalyzingRef.current = false;
        }
      },
      "image/jpeg",
      0.8,
    );
  }, [cameraId, location, onIncidentCreated]);

  const startCamera = useCallback(async () => {
    setErrorMessage(null);
    setStatus("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setStatus("live");
      intervalRef.current = setInterval(captureAndAnalyze, CAPTURE_INTERVAL_MS);
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setStatus("denied");
      } else if (name === "NotFoundError" || name === "DevicesNotFoundError") {
        setStatus("unavailable");
        setErrorMessage("No camera device was found on this system.");
      } else {
        setStatus("unavailable");
        setErrorMessage(err instanceof Error ? err.message : "Could not access the camera.");
      }
    }
  }, [captureAndAnalyze]);

  const timestamp = now.toLocaleTimeString("en-US", { hour12: false });
  const isLive = status === "live";

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-2xl border border-border bg-[#05060a]">
      <canvas ref={canvasRef} className="hidden" />

      {/* Real webcam feed */}
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        className={`absolute inset-0 h-full w-full object-cover ${isLive ? "opacity-100" : "opacity-0"}`}
      />

      {!isLive && (
        <>
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_20%,rgba(91,124,250,0.14),transparent_55%),radial-gradient(ellipse_at_75%_75%,rgba(139,107,245,0.10),transparent_50%)]" />
          <div className="absolute inset-0 bg-grid opacity-40" />
          <div className="pointer-events-none absolute inset-0 overflow-hidden">
            <div className="absolute inset-x-0 h-24 animate-scan bg-linear-to-b from-transparent via-accent/10 to-transparent" />
          </div>
        </>
      )}

      {/* Center state overlay: idle / requesting / denied / unavailable.
          Plain conditional rendering, deliberately not AnimatePresence --
          this component re-renders every second (the clock), and
          AnimatePresence's exit tracking was observed getting stuck with
          overlapping content under that steady re-render pressure combined
          with the idle->requesting->live transition happening in rapid
          succession. */}
      {status === "idle" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-surface-3 text-ink-dim">
            <Camera size={22} />
          </div>
          <p className="text-sm font-semibold text-ink">Camera Offline</p>
          <p className="max-w-xs text-xs text-ink-faint">
            Start your browser camera to begin real-time AI monitoring.
          </p>
          <Button onClick={startCamera} icon={<Video size={15} />} className="mt-1">
            Start Camera
          </Button>
        </div>
      )}

      {status === "requesting" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-center">
          <Loader2 size={22} className="animate-spin text-accent" />
          <p className="text-sm font-medium text-ink-dim">Requesting camera permission…</p>
        </div>
      )}

      {status === "denied" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-critical/10 text-critical">
            <ShieldAlert size={22} />
          </div>
          <p className="text-sm font-semibold text-ink">Camera Permission Denied</p>
          <p className="max-w-xs text-xs text-ink-faint">
            Allow camera access in your browser's site settings, then try again.
          </p>
          <Button onClick={startCamera} variant="secondary" className="mt-1">
            Try Again
          </Button>
        </div>
      )}

      {status === "unavailable" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-warn/10 text-warn">
            <AlertTriangle size={22} />
          </div>
          <p className="text-sm font-semibold text-ink">Camera Unavailable</p>
          <p className="max-w-xs text-xs text-ink-faint">{errorMessage ?? "The camera could not be started."}</p>
          <Button onClick={startCamera} variant="secondary" className="mt-1">
            Try Again
          </Button>
        </div>
      )}

      {/* Live detection badge -- only ever reflects a real analyzeFrame result */}
      {isLive && lastResult && lastResult.status !== "NORMAL" && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          className="absolute left-1/2 top-14 -translate-x-1/2 rounded-full border border-critical/40 bg-critical/90 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-white shadow-[0_0_16px_rgba(248,85,90,0.5)]"
        >
          {lastResult.event.label} · {Math.round(lastResult.event.confidence * 100)}%
        </motion.div>
      )}

      {/* Top overlay row */}
      <div className="absolute inset-x-0 top-0 flex items-start justify-between p-4">
        <div className="flex items-center gap-2 rounded-md bg-black/50 px-2.5 py-1.5 backdrop-blur-sm">
          <span className="relative flex h-2 w-2">
            {isLive && (
              <span className="absolute inline-flex h-full w-full animate-pulse-slow rounded-full bg-critical opacity-75" />
            )}
            <span className={`relative inline-flex h-2 w-2 rounded-full ${isLive ? "bg-critical" : "bg-ink-faint"}`} />
          </span>
          <span className="text-[11px] font-bold uppercase tracking-widest text-white">
            {isLive ? "Live" : "Offline"}
          </span>
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
          {isLive && (
            <button
              onClick={stopCamera}
              aria-label="Stop camera"
              className="flex items-center gap-1.5 rounded-md bg-black/50 px-2.5 py-1.5 text-white/80 backdrop-blur-sm transition-colors hover:bg-critical/80 hover:text-white"
            >
              <VideoOff size={13} />
              <span className="text-[11px] font-semibold">Stop</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
