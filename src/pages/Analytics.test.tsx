import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Analytics from "./Analytics";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import { getAnalyticsData } from "@/services/api";
import type { AnalyticsData } from "@/services/api";

vi.mock("@/services/api", () => ({
  getAnalyticsData: vi.fn(),
}));

const mockGetAnalyticsData = vi.mocked(getAnalyticsData);

const POPULATED: AnalyticsData = {
  eventsOverTime: [{ time: "10:00", events: 3 }],
  riskDistribution: [
    { name: "HIGH", value: 1 },
    { name: "MEDIUM", value: 0 },
    { name: "LOW", value: 0 },
  ],
  eventCategories: [{ name: "Restricted Area Entry", value: 1 }],
  systemHealth: { uptime: "99.9%", avgResponseTime: "1.0s", edgeNodesOnline: 1, edgeNodesTotal: 1 },
};

// What a genuinely fresh/empty database returns -- this is the shape that
// exposed the missing defensive handling (empty chart arrays, an
// all-zero risk distribution) rather than being an invalid response.
const EMPTY: AnalyticsData = {
  eventsOverTime: [],
  riskDistribution: [
    { name: "LOW", value: 0 },
    { name: "MEDIUM", value: 0 },
    { name: "HIGH", value: 0 },
  ],
  eventCategories: [],
  systemHealth: { uptime: "99.98%", avgResponseTime: "1.4s", edgeNodesOnline: 1, edgeNodesTotal: 1 },
};

beforeEach(() => {
  mockGetAnalyticsData.mockReset();
});

describe("Analytics page", () => {
  it("shows a loading state before data arrives", async () => {
    let resolve!: (value: AnalyticsData) => void;
    mockGetAnalyticsData.mockReturnValue(new Promise((res) => (resolve = res)));

    render(<Analytics />);
    expect(screen.getByText(/loading analytics/i)).toBeInTheDocument();

    resolve(POPULATED);
    expect(await screen.findByText(/events over time/i)).toBeInTheDocument();
  });

  it("renders real data from the backend once loaded", async () => {
    mockGetAnalyticsData.mockResolvedValue(POPULATED);
    render(<Analytics />);

    expect(await screen.findByText(/events over time/i)).toBeInTheDocument();
    expect(screen.getByText("99.9%")).toBeInTheDocument();
    expect(screen.getByText("1/1")).toBeInTheDocument();
    expect(screen.getByText("Event Categories")).toBeInTheDocument();
    // Recharts skips drawing its internal SVG text under jsdom's 0-size
    // layout, so the reliable, environment-independent signal that real
    // (non-empty) data reached the chart is that the empty-state guard
    // added for this fix did NOT trigger -- verified in a real browser
    // separately.
    expect(screen.queryByText("No event data available yet.")).not.toBeInTheDocument();
  });

  it("shows an error state with retry instead of a blank page when the API fails", async () => {
    mockGetAnalyticsData.mockRejectedValueOnce(new Error("Cannot reach the EdgePilot backend."));
    const user = userEvent.setup();
    render(<Analytics />);

    expect(await screen.findByText("Cannot reach the EdgePilot backend.")).toBeInTheDocument();

    mockGetAnalyticsData.mockResolvedValueOnce(POPULATED);
    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(await screen.findByText(/events over time/i)).toBeInTheDocument();
  });

  it("renders a real, non-blank page for a fresh/empty database instead of crashing", async () => {
    mockGetAnalyticsData.mockResolvedValue(EMPTY);
    render(<Analytics />);

    expect(await screen.findByText(/events over time/i)).toBeInTheDocument();
    // Every chart explicitly says there's no data yet, rather than
    // rendering a broken-looking empty chart or throwing.
    expect(screen.getAllByText("No event data available yet.")).toHaveLength(3);
    // The summary row still computes honestly from real (zero) data.
    expect(screen.getByText("0", { selector: "p" })).toBeInTheDocument();
  });

  it("never lets a chart crash take down more than its own page content", async () => {
    mockGetAnalyticsData.mockResolvedValue(POPULATED);
    vi.spyOn(console, "error").mockImplementation(() => {});

    // Force a crash the same way a real third-party rendering failure
    // would surface, and confirm the ErrorBoundary this page is wrapped
    // in during real navigation (see Layout.tsx) actually contains it.
    function Boom(): never {
      throw new Error("Simulated Recharts crash");
    }

    render(
      <div>
        <p>Sidebar placeholder</p>
        <ErrorBoundary>
          <Boom />
        </ErrorBoundary>
      </div>,
    );

    expect(screen.getByText("Sidebar placeholder")).toBeInTheDocument();
    expect(screen.getByText("This page failed to load.")).toBeInTheDocument();
  });
});
