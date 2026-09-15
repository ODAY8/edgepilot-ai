import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import AnalysisResultCard from "@/components/analysis/AnalysisResultCard";
import ProcessingState, { type ProcessingStage } from "@/components/analysis/ProcessingState";
import UploadZone from "@/components/analysis/UploadZone";
import Button from "@/components/common/Button";
import ErrorState from "@/components/common/ErrorState";
import { acknowledgeIncident, analyzeInput, escalateIncident, type AnalysisResult } from "@/services/api";

type Stage = "upload" | "processing" | "result" | "error";

export default function Analyze() {
  const [stage, setStage] = useState<Stage>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [processingStage, setProcessingStage] = useState<ProcessingStage>("analyzing");

  // The processing UI stays up for exactly as long as the real request is
  // pending -- it's driven by analyzeInput's actual lifecycle (below), never
  // by a fixed timer standing in for how long the AI pipeline "should" take.
  const startAnalysis = async () => {
    if (!file) return;
    setStage("processing");
    setProcessingStage("analyzing");
    try {
      const analysis = await analyzeInput(file, () => setProcessingStage("finalizing"));
      setResult(analysis);
      setStage("result");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
      setStage("error");
    }
  };

  const reset = () => {
    setFile(null);
    setResult(null);
    setError(null);
    setStage("upload");
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <motion.div
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <h2 className="text-xl font-bold text-ink sm:text-2xl">Analyze Environment</h2>
        <p className="mt-1 text-sm text-ink-dim">
          Upload visual data and let EdgePilot identify meaningful events.
        </p>
      </motion.div>

      <AnimatePresence mode="wait">
        {stage === "upload" && (
          <motion.div
            key="upload"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="space-y-5"
          >
            <UploadZone file={file} onFileSelected={setFile} onClear={() => setFile(null)} />
            <Button className="w-full sm:w-auto" onClick={startAnalysis} disabled={!file}>
              Start AI Analysis
            </Button>
          </motion.div>
        )}

        {stage === "processing" && (
          <motion.div key="processing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <ProcessingState stage={processingStage} />
          </motion.div>
        )}

        {stage === "result" && result && (
          <motion.div key="result" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <AnalysisResultCard
              result={result}
              onAcknowledge={() => acknowledgeIncident(result.id).then(() => undefined)}
              onEscalate={() => escalateIncident(result.id).then(() => undefined)}
              onAnalyzeAnother={reset}
            />
          </motion.div>
        )}

        {stage === "error" && error && (
          <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <ErrorState message={error} onRetry={reset} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
