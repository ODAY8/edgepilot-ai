import { motion } from "framer-motion";
import { FileVideo, UploadCloud, X } from "lucide-react";
import { type DragEvent, useRef, useState } from "react";
import Button from "@/components/common/Button";

interface UploadZoneProps {
  file: File | null;
  onFileSelected: (file: File) => void;
  onClear: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadZone({ file, onFileSelected, onClear }: UploadZoneProps) {
  const [dragActive, setDragActive] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragActive(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) onFileSelected(dropped);
  };

  if (file) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between gap-4 rounded-2xl border border-border bg-surface p-5"
      >
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
            <FileVideo size={20} />
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-ink">{file.name}</p>
            <p className="text-xs text-ink-faint">{formatBytes(file.size)}</p>
          </div>
        </div>
        <button
          onClick={onClear}
          aria-label="Remove file"
          className="shrink-0 rounded-lg p-2 text-ink-dim transition-colors hover:bg-surface-3 hover:text-ink"
        >
          <X size={16} />
        </button>
      </motion.div>
    );
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={handleDrop}
      className={`relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-12 text-center transition-colors duration-200 ${
        dragActive ? "border-accent bg-accent-soft" : "border-border bg-surface hover:border-accent/40"
      }`}
    >
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-soft text-accent">
        <UploadCloud size={26} />
      </div>
      <p className="mt-4 text-sm font-semibold text-ink">Drag &amp; drop video here</p>
      <p className="mt-1 text-xs text-ink-faint">or</p>
      <Button
        variant="secondary"
        className="mt-3"
        onClick={() => inputRef.current?.click()}
      >
        Select Video
      </Button>
      <p className="mt-4 text-[11px] text-ink-faint">Supports MP4, MOV, WEBM, JPG, PNG · Up to 500MB</p>
      <input
        ref={inputRef}
        type="file"
        accept="video/*,image/*"
        className="hidden"
        onChange={(e) => {
          const selected = e.target.files?.[0];
          if (selected) onFileSelected(selected);
        }}
      />
    </div>
  );
}
