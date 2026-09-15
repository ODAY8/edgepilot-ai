import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Settings from "./Settings";
import { getSystemStatus } from "@/services/api";
import type { SystemStatus } from "@/services/api";

vi.mock("@/services/api", () => ({
  getSystemStatus: vi.fn(),
}));

const mockGetSystemStatus = vi.mocked(getSystemStatus);

const CONFIGURED: SystemStatus = { version: "1.0.0", visionEnabled: true, reasoningEnabled: true };
const PARTIALLY_CONFIGURED: SystemStatus = { version: "1.0.0", visionEnabled: true, reasoningEnabled: false };

beforeEach(() => {
  mockGetSystemStatus.mockReset();
});

describe("Settings page", () => {
  it("shows API status, version, and provider state once loaded", async () => {
    mockGetSystemStatus.mockResolvedValue(CONFIGURED);
    render(<Settings />);

    expect(await screen.findByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("v1.0.0")).toBeInTheDocument();
    expect(screen.getAllByText("Enabled")).toHaveLength(2);
  });

  it("labels a disabled provider honestly instead of always claiming enabled", async () => {
    mockGetSystemStatus.mockResolvedValue(PARTIALLY_CONFIGURED);
    render(<Settings />);

    await screen.findByText("Connected");
    expect(screen.getByText("Enabled")).toBeInTheDocument();
    expect(screen.getByText("Disabled")).toBeInTheDocument();
  });

  it("shows Unreachable with a retry option when the backend can't be reached, instead of inventing a status", async () => {
    const user = userEvent.setup();
    mockGetSystemStatus.mockRejectedValueOnce(new Error("network error")).mockResolvedValueOnce(CONFIGURED);
    render(<Settings />);

    expect(await screen.findByText("Unreachable")).toBeInTheDocument();
    expect(screen.getByText("Unavailable", { selector: "p" })).toBeInTheDocument();
    expect(screen.queryByText("v1.0.0")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /retry/i }));

    expect(await screen.findByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("v1.0.0")).toBeInTheDocument();
  });

  it("never displays anything resembling a raw API key", async () => {
    mockGetSystemStatus.mockResolvedValue(CONFIGURED);
    const { container } = render(<Settings />);

    await screen.findByText("Connected");
    expect(container.textContent).not.toMatch(/AIza|gsk_|sk-[a-zA-Z0-9]{10,}/);
  });

  it("reports live camera support via feature detection, not a hardcoded claim", async () => {
    mockGetSystemStatus.mockResolvedValue(CONFIGURED);
    const original = navigator.mediaDevices;
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });

    render(<Settings />);
    await waitFor(() => expect(screen.getByText("Live Camera")).toBeInTheDocument());
    expect(screen.getByText("Not supported by this browser")).toBeInTheDocument();

    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: original });
  });
});
