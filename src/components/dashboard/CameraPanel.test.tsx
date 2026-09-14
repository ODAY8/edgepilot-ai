import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import CameraPanel from "./CameraPanel";
import { analyzeFrame } from "@/services/api";
import type { LiveFrameResult } from "@/services/api";

vi.mock("@/services/api", () => ({
  analyzeFrame: vi.fn(),
}));

const mockAnalyzeFrame = vi.mocked(analyzeFrame);

const NORMAL_RESULT: LiveFrameResult = {
  incidentCreated: false,
  status: "NORMAL",
  event: { type: "normal_activity", label: "Normal Activity", confidence: 0.95 },
  risk: { level: "LOW", score: 5 },
  incidentId: null,
  analysis: null,
  recommendation: null,
  objects: [
    { name: "person", confidence: 0.98, context: "seated at a workstation" },
    { name: "laptop", confidence: 0.97, context: "on the desk" },
  ],
  sceneDescription: "Person seated at a workstation using a laptop.",
};

const MEANINGFUL_RESULT: LiveFrameResult = {
  incidentCreated: true,
  status: "CREATED",
  event: { type: "ppe_violation", label: "PPE Violation", confidence: 0.9 },
  risk: { level: "MEDIUM", score: 60 },
  incidentId: "INC-TEST",
  analysis: { summary: "s", explanation: "e" },
  recommendation: { action: "a", priority: "HIGH" },
  objects: [{ name: "person", confidence: 0.99, context: "missing hard hat" }],
  sceneDescription: "Person working without required head protection.",
};

function mockGetUserMedia() {
  const fakeStream = { getTracks: () => [{ stop: vi.fn() }] } as unknown as MediaStream;
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue(fakeStream) },
  });
}

function markVideoReady(container: HTMLElement) {
  const video = container.querySelector("video") as HTMLVideoElement;
  Object.defineProperty(video, "readyState", { configurable: true, value: 2 });
  Object.defineProperty(video, "videoWidth", { configurable: true, value: 640 });
  Object.defineProperty(video, "videoHeight", { configurable: true, value: 480 });
}

async function startCamera(container: HTMLElement, user: ReturnType<typeof userEvent.setup>) {
  markVideoReady(container);
  await user.click(screen.getByRole("button", { name: /start camera/i }));
  await waitFor(() => expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument());
}

async function advanceOneCaptureCycle() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(4000);
  });
}

beforeEach(() => {
  // Only fake setInterval/clearInterval -- the capture loop's only timer
  // API. Leaving setTimeout real keeps Testing Library's waitFor/findBy
  // polling (which relies on real setTimeout) from deadlocking against an
  // un-advanced fake clock.
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] });
  mockGetUserMedia();
  HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({ drawImage: vi.fn() }) as unknown as typeof HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.toBlob = vi.fn(function (this: HTMLCanvasElement, callback: BlobCallback) {
    callback(new Blob(["fake"], { type: "image/jpeg" }));
  }) as unknown as typeof HTMLCanvasElement.prototype.toBlob;
  mockAnalyzeFrame.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("CameraPanel camera constraints", () => {
  it("requests a 1280x720-ideal environment-facing camera stream", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const { container } = render(<CameraPanel />);

    await startCamera(container, user);

    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "environment" },
      audio: false,
    });
  });
});

describe("CameraPanel vision-failure handling", () => {
  it("surfaces a failed frame as Vision Unavailable, not All Clear, and never creates an incident", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockAnalyzeFrame.mockRejectedValueOnce(new Error("Vision analysis is not configured (GEMINI_API_KEY is not set)."));

    const onVisionError = vi.fn();
    const onFrameResult = vi.fn();
    const onIncidentCreated = vi.fn();

    const { container } = render(
      <CameraPanel onFrameResult={onFrameResult} onVisionError={onVisionError} onIncidentCreated={onIncidentCreated} />,
    );

    await startCamera(container, user);
    await advanceOneCaptureCycle();

    expect(onVisionError).toHaveBeenCalledWith("Vision analysis is not configured (GEMINI_API_KEY is not set).");
    expect(onFrameResult).not.toHaveBeenCalled();
    expect(onIncidentCreated).not.toHaveBeenCalled();
    expect(screen.getByText(/vision unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText(/all clear/i)).not.toBeInTheDocument();
  });

  it("keeps the capture loop running on schedule after a failure and recovers on the next success", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockAnalyzeFrame.mockRejectedValueOnce(new Error("network hiccup")).mockResolvedValueOnce(NORMAL_RESULT);

    const onVisionError = vi.fn();
    const onFrameResult = vi.fn();

    const { container } = render(<CameraPanel onFrameResult={onFrameResult} onVisionError={onVisionError} />);

    await startCamera(container, user);
    await advanceOneCaptureCycle();
    expect(mockAnalyzeFrame).toHaveBeenCalledTimes(1);
    expect(onVisionError).toHaveBeenLastCalledWith("network hiccup");
    // The loop itself must not have stopped -- still live, not reverted to idle.
    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument();

    await advanceOneCaptureCycle();
    expect(mockAnalyzeFrame).toHaveBeenCalledTimes(2);
    expect(onVisionError).toHaveBeenLastCalledWith(null);
    expect(onFrameResult).toHaveBeenLastCalledWith(NORMAL_RESULT);
    expect(screen.queryByText(/vision unavailable/i)).not.toBeInTheDocument();
  });

  it("replaces a stale detection badge with Vision Unavailable on a later failure", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockAnalyzeFrame.mockResolvedValueOnce(MEANINGFUL_RESULT).mockRejectedValueOnce(new Error("temporary outage"));

    const { container } = render(<CameraPanel />);

    await startCamera(container, user);
    await advanceOneCaptureCycle();
    expect(await screen.findByText(/PPE Violation/i)).toBeInTheDocument();

    await advanceOneCaptureCycle();
    expect(screen.getByText(/vision unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText(/PPE Violation/i)).not.toBeInTheDocument();
  });

  it("clears the vision-error state when the camera is stopped", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockAnalyzeFrame.mockRejectedValueOnce(new Error("boom"));
    const onVisionError = vi.fn();

    const { container } = render(<CameraPanel onVisionError={onVisionError} />);

    await startCamera(container, user);
    await advanceOneCaptureCycle();
    expect(screen.getByText(/vision unavailable/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /stop/i }));
    expect(onVisionError).toHaveBeenLastCalledWith(null);
    expect(screen.queryByText(/vision unavailable/i)).not.toBeInTheDocument();
  });

  it("does not skip the next scheduled capture just because the previous one failed", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockAnalyzeFrame.mockRejectedValue(new Error("still down"));

    const { container } = render(<CameraPanel />);
    await startCamera(container, user);

    await advanceOneCaptureCycle();
    await advanceOneCaptureCycle();
    await advanceOneCaptureCycle();

    expect(mockAnalyzeFrame).toHaveBeenCalledTimes(3);
  });
});

describe("CameraPanel scene understanding panel", () => {
  it("shows detected objects and scene description alongside a normal frame", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockAnalyzeFrame.mockResolvedValueOnce(NORMAL_RESULT);

    const { container } = render(<CameraPanel />);
    await startCamera(container, user);
    await advanceOneCaptureCycle();

    expect(await screen.findByText("Detected Objects")).toBeInTheDocument();
    expect(screen.getByText(/person · 98%/i)).toBeInTheDocument();
    expect(screen.getByText(/laptop · 97%/i)).toBeInTheDocument();
    expect(screen.getByText("Person seated at a workstation using a laptop.")).toBeInTheDocument();
    // Safety status itself isn't duplicated in this panel -- it's already
    // shown elsewhere on the dashboard (Current Incident / All Clear).
    expect(screen.queryByText(/all clear/i)).not.toBeInTheDocument();
  });

  it("still shows detected objects and scene when a safety event is created", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockAnalyzeFrame.mockResolvedValueOnce(MEANINGFUL_RESULT);

    const { container } = render(<CameraPanel />);
    await startCamera(container, user);
    await advanceOneCaptureCycle();

    expect(await screen.findByText("Detected Objects")).toBeInTheDocument();
    expect(screen.getByText(/person · 99%/i)).toBeInTheDocument();
    expect(screen.getByText("Person working without required head protection.")).toBeInTheDocument();
    // The existing detection badge behavior is untouched.
    expect(screen.getByText(/PPE Violation/i)).toBeInTheDocument();
  });

  it("hides the scene panel while vision is unavailable", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockAnalyzeFrame.mockResolvedValueOnce(NORMAL_RESULT).mockRejectedValueOnce(new Error("boom"));

    const { container } = render(<CameraPanel />);
    await startCamera(container, user);
    await advanceOneCaptureCycle();
    expect(await screen.findByText("Detected Objects")).toBeInTheDocument();

    await advanceOneCaptureCycle();
    expect(screen.getByText(/vision unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText("Detected Objects")).not.toBeInTheDocument();
  });

  it("renders nothing extra when there are no objects and no scene description", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockAnalyzeFrame.mockResolvedValueOnce({
      ...NORMAL_RESULT,
      objects: [],
      sceneDescription: "",
    });

    const { container } = render(<CameraPanel />);
    await startCamera(container, user);
    await advanceOneCaptureCycle();

    await waitFor(() => expect(mockAnalyzeFrame).toHaveBeenCalledTimes(1));
    expect(screen.queryByText("Detected Objects")).not.toBeInTheDocument();
    expect(screen.queryByText("Scene")).not.toBeInTheDocument();
  });
});
