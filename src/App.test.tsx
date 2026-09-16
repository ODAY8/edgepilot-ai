import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import * as api from "@/services/api";
import type { AnalyticsData, SystemStatus } from "@/services/api";
import type { DashboardStats, Incident } from "@/data/types";

vi.mock("@/services/api", () => ({
  getDashboardStats: vi.fn(),
  getIncidents: vi.fn(),
  getAnalyticsData: vi.fn(),
  getSystemStatus: vi.fn(),
  acknowledgeIncident: vi.fn(),
  escalateIncident: vi.fn(),
  analyzeInput: vi.fn(),
  analyzeFrame: vi.fn(),
}));

// These route/navigation tests exercise page content behind protected
// routes, not auth itself -- stub Supabase to resolve as an
// already-signed-in session so AuthProvider settles immediately instead
// of making a real network call to a Supabase project that doesn't exist
// in the test environment.
vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: { session: { user: { id: "test-user", email: "operator@edgepilot.test" } } },
      }),
      onAuthStateChange: vi.fn(() => ({ data: { subscription: { unsubscribe: vi.fn() } } } as never)),
      signOut: vi.fn().mockResolvedValue({ error: null }),
      signInWithPassword: vi.fn(),
      signUp: vi.fn(),
    },
  },
}));

const STATS: DashboardStats = {
  totalEvents: { value: 10, change: 0 },
  highRisk: { value: 2, change: 0 },
  activeInputs: { value: 1, change: 0 },
  systemHealth: { value: 98, change: 0 },
};

const INCIDENTS: Incident[] = [
  {
    id: "INC-1",
    event: "Restricted Area Entry",
    risk: "HIGH",
    confidence: 90,
    location: "Zone A",
    cameraId: "CAM-01",
    edgeNode: "EDGE 01",
    timestamp: "10:00:00",
    date: "2026-09-14",
    explanation: "A person entered the restricted zone.",
    recommendation: "Notify the safety officer.",
    status: "ACTIVE",
    detection: "Person detected",
    context: "Restricted zone",
  },
];

const ANALYTICS: AnalyticsData = {
  eventsOverTime: [{ time: "10:00", events: 3 }],
  riskDistribution: [
    { name: "HIGH", value: 1 },
    { name: "MEDIUM", value: 0 },
    { name: "LOW", value: 0 },
  ],
  eventCategories: [{ name: "Restricted Area Entry", value: 1 }],
  systemHealth: { uptime: "99.9%", avgResponseTime: "1.0s", edgeNodesOnline: 1, edgeNodesTotal: 1 },
};

const SYSTEM_STATUS: SystemStatus = { version: "1.0.0", visionEnabled: true, reasoningEnabled: true };

function goTo(path: string) {
  window.history.pushState({}, "", path);
}

// Per-page assertions that only ever match one thing, even though the app
// legitimately renders some text twice (TopBar title + page heading,
// desktop table + mobile card layout both present in jsdom, two landing
// CTAs) -- these checks are written to survive that instead of asserting
// single-match text that would be a false positive on app structure.
const PAGE_CHECKS: Record<string, () => Promise<unknown>> = {
  dashboard: () => screen.findByText(/good evening, operator/i),
  analyze: () => screen.findByRole("button", { name: /start ai analysis/i }),
  incidents: () => screen.findAllByText("Restricted Area Entry"),
  analytics: () => screen.findByText(/events over time/i),
  settings: () => screen.findByText("Connected"),
};

beforeEach(() => {
  vi.mocked(api.getDashboardStats).mockResolvedValue(STATS);
  vi.mocked(api.getIncidents).mockResolvedValue(INCIDENTS);
  vi.mocked(api.getAnalyticsData).mockResolvedValue(ANALYTICS);
  vi.mocked(api.getSystemStatus).mockResolvedValue(SYSTEM_STATUS);
  goTo("/dashboard");
});

describe("Route loading (direct navigation / refresh equivalent)", () => {
  it("loads the Dashboard route directly", async () => {
    goTo("/dashboard");
    render(<App />);
    await PAGE_CHECKS.dashboard();
    expect(await screen.findByText("Total Events")).toBeInTheDocument();
  });

  it("loads the Analyze route directly", async () => {
    goTo("/analyze");
    render(<App />);
    expect(await PAGE_CHECKS.analyze()).toBeInTheDocument();
  });

  it("loads the Incidents route directly", async () => {
    goTo("/incidents");
    render(<App />);
    const matches = await PAGE_CHECKS.incidents();
    expect((matches as unknown[]).length).toBeGreaterThan(0);
  });

  it("loads the Analytics route directly", async () => {
    goTo("/analytics");
    render(<App />);
    expect(await PAGE_CHECKS.analytics()).toBeInTheDocument();
  });

  it("loads the Settings route directly", async () => {
    goTo("/settings");
    render(<App />);
    expect(await PAGE_CHECKS.settings()).toBeInTheDocument();
    expect(screen.getByText("v1.0.0")).toBeInTheDocument();
    expect(screen.getAllByText("Enabled").length).toBeGreaterThan(0);
  });

  it("redirects an unknown route to the landing page", async () => {
    goTo("/this-route-does-not-exist");
    render(<App />);
    expect(await screen.findAllByText(/launch dashboard/i)).not.toHaveLength(0);
  });
});

describe("Sidebar navigation", () => {
  it("navigates to every page by clicking its sidebar link and marks it active", async () => {
    const user = userEvent.setup();
    render(<App />);
    await PAGE_CHECKS.dashboard();

    const cases: { name: RegExp; check: () => Promise<unknown> }[] = [
      { name: /^analyze$/i, check: PAGE_CHECKS.analyze },
      { name: /^incidents$/i, check: PAGE_CHECKS.incidents },
      { name: /^analytics$/i, check: PAGE_CHECKS.analytics },
      { name: /^settings$/i, check: PAGE_CHECKS.settings },
      { name: /^dashboard$/i, check: PAGE_CHECKS.dashboard },
    ];

    for (const { name, check } of cases) {
      const link = screen.getByRole("link", { name });
      await user.click(link);
      // AnimatePresence's exit/enter transition plus the lazy-loaded page
      // chunk both add a little real delay in the test environment.
      await check();
      expect(link).toHaveAttribute("aria-current", "page");
    }
  });

  it("supports browser back navigation between pages", async () => {
    const user = userEvent.setup();
    render(<App />);
    await PAGE_CHECKS.dashboard();

    await user.click(screen.getByRole("link", { name: /^analytics$/i }));
    await PAGE_CHECKS.analytics();

    await act(async () => {
      window.history.back();
    });

    await PAGE_CHECKS.dashboard();
  });
});

describe("TopBar controls", () => {
  it("the notification bell is a real link to Incidents", async () => {
    render(<App />);
    await PAGE_CHECKS.dashboard();

    const bell = screen.getByRole("link", { name: /view incidents/i });
    expect(bell).toHaveAttribute("href", "/incidents");
  });

  it("does not expose a fake, non-functional user menu button", async () => {
    render(<App />);
    await PAGE_CHECKS.dashboard();

    expect(screen.queryByRole("button", { name: /user menu/i })).not.toBeInTheDocument();
  });
});
