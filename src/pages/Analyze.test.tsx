import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Analyze from "./Analyze";
import { analyzeInput } from "@/services/api";
import type { AnalysisResult } from "@/services/api";

vi.mock("@/services/api", () => ({
  analyzeInput: vi.fn(),
  acknowledgeIncident: vi.fn(),
  escalateIncident: vi.fn(),
}));

const mockAnalyzeInput = vi.mocked(analyzeInput);

const RESULT: AnalysisResult = {
  id: "INC-TEST",
  event: "Restricted Area Entry",
  risk: "HIGH",
  confidence: 96,
  explanation: "A person is inside the marked restricted zone.",
  recommendation: "Notify the safety officer.",
  detection: "Restricted Area Entry",
  context: "Zone A",
  timestamp: "14:00:00",
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

async function uploadAndStart(container: HTMLElement, user: ReturnType<typeof userEvent.setup>) {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File(["fake video bytes"], "clip.mp4", { type: "video/mp4" });
  await user.upload(input, file);
  await user.click(screen.getByRole("button", { name: /start ai analysis/i }));
}

beforeEach(() => {
  mockAnalyzeInput.mockReset();
});

describe("Analyze page processing lifecycle", () => {
  it("keeps the pipeline steps active (not fake-completed) while the real request is still pending", async () => {
    const user = userEvent.setup();
    const { promise } = deferred<AnalysisResult>();
    mockAnalyzeInput.mockReturnValue(promise);

    const { container } = render(<Analyze />);
    await uploadAndStart(container, user);

    // The processing view must be up, and none of the AI-pipeline steps or
    // "Complete" may be shown as done -- the real request hasn't resolved.
    expect(await screen.findByText("Upload received")).toBeInTheDocument();
    expect(screen.getByText("Analyzing image/video with Gemini")).toBeInTheDocument();
    expect(screen.getByText("Evaluating risk")).toBeInTheDocument();
    expect(screen.getByText("Generating AI reasoning")).toBeInTheDocument();
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.queryByText("Restricted Area Entry")).not.toBeInTheDocument();

    // Never resolved in this test -- proves the UI doesn't advance on its own.
  });

  it("only shows the result once the real request actually resolves", async () => {
    const user = userEvent.setup();
    const { promise, resolve } = deferred<AnalysisResult>();
    mockAnalyzeInput.mockReturnValue(promise);

    const { container } = render(<Analyze />);
    await uploadAndStart(container, user);

    expect(await screen.findByText("Upload received")).toBeInTheDocument();
    expect(screen.queryByText(RESULT.event)).not.toBeInTheDocument();

    resolve(RESULT);

    expect(await screen.findByText(RESULT.event)).toBeInTheDocument();
    expect(screen.getByText(/confidence: 96%/i)).toBeInTheDocument();
    expect(screen.queryByText("Analyzing image/video with Gemini")).not.toBeInTheDocument();
  });

  it("shows an error state instead of pretending processing completed when the request fails", async () => {
    const user = userEvent.setup();
    const { promise, reject } = deferred<AnalysisResult>();
    mockAnalyzeInput.mockReturnValue(promise);

    const { container } = render(<Analyze />);
    await uploadAndStart(container, user);

    reject(new Error("Vision analysis failed: Gemini timed out."));

    expect(await screen.findByText(/vision analysis failed: gemini timed out/i)).toBeInTheDocument();
    expect(screen.queryByText("Complete")).not.toBeInTheDocument();
    expect(screen.queryByText(RESULT.event)).not.toBeInTheDocument();
  });

  it("marks the AI-pipeline steps done only after analyzeInput signals the heavy request has returned", async () => {
    const user = userEvent.setup();
    let onAnalyzed: (() => void) | undefined;
    const { promise, resolve } = deferred<AnalysisResult>();
    mockAnalyzeInput.mockImplementation((_file, cb) => {
      onAnalyzed = cb;
      return promise;
    });

    const { container } = render(<Analyze />);
    await uploadAndStart(container, user);

    await waitFor(() => expect(onAnalyzed).toBeDefined());
    expect(await screen.findByText("Analyzing image/video with Gemini")).toBeInTheDocument();

    // Simulate the real /api/analyze response having come back, before the
    // follow-up incident-detail fetch resolves.
    onAnalyzed!();
    await waitFor(() => {
      const item = screen.getByText("Analyzing image/video with Gemini").closest("li");
      const iconSpan = item?.querySelector("span");
      expect(iconSpan?.className).toContain("border-safe");
    });

    resolve(RESULT);
    expect(await screen.findByText(RESULT.event)).toBeInTheDocument();
  });
});
