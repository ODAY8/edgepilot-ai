import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, getDashboardStats } from "@/services/api";
import { supabase } from "@/lib/supabase";

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn(),
      signOut: vi.fn(),
    },
  },
}));

const mockGetSession = vi.mocked(supabase.auth.getSession);
const mockSignOut = vi.mocked(supabase.auth.signOut);

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: async () => body,
  } as Response;
}

beforeEach(() => {
  mockSignOut.mockResolvedValue({ error: null });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("apiFetch authentication", () => {
  it("attaches the current Supabase access token as a Bearer header", async () => {
    mockGetSession.mockResolvedValue({
      data: { session: { access_token: "the-current-token" } },
    } as never);
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(200, { totalEvents: { value: 0, change: 0 }, highRisk: { value: 0, change: 0 }, activeInputs: { value: 0, change: 0 }, systemHealth: { value: 100, change: 0 } }),
    );

    await getDashboardStats();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, init] = fetchSpy.mock.calls[0];
    const headers = init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer the-current-token");
  });

  it("re-reads the session on every call instead of reusing a cached token", async () => {
    mockGetSession
      .mockResolvedValueOnce({ data: { session: { access_token: "token-1" } } } as never)
      .mockResolvedValueOnce({ data: { session: { access_token: "token-2" } } } as never);
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(200, { totalEvents: { value: 0, change: 0 }, highRisk: { value: 0, change: 0 }, activeInputs: { value: 0, change: 0 }, systemHealth: { value: 100, change: 0 } }));

    await getDashboardStats();
    await getDashboardStats();

    expect(mockGetSession).toHaveBeenCalledTimes(2);
    const firstHeaders = fetchSpy.mock.calls[0][1]?.headers as Record<string, string>;
    const secondHeaders = fetchSpy.mock.calls[1][1]?.headers as Record<string, string>;
    expect(firstHeaders.Authorization).toBe("Bearer token-1");
    expect(secondHeaders.Authorization).toBe("Bearer token-2");
  });

  it("sends no Authorization header when there is no session", async () => {
    mockGetSession.mockResolvedValue({ data: { session: null } } as never);
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse(200, { totalEvents: { value: 0, change: 0 }, highRisk: { value: 0, change: 0 }, activeInputs: { value: 0, change: 0 }, systemHealth: { value: 100, change: 0 } }),
    );

    await getDashboardStats();

    const headers = fetchSpy.mock.calls[0][1]?.headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it("on a 401, signs out locally (no Supabase network call) and throws a clear error", async () => {
    mockGetSession.mockResolvedValue({ data: { session: { access_token: "stale-or-rejected" } } } as never);
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(401, { detail: "Missing or invalid Authorization header." }));

    await expect(getDashboardStats()).rejects.toMatchObject({
      status: 401,
    } satisfies Partial<ApiError>);

    expect(mockSignOut).toHaveBeenCalledWith({ scope: "local" });
  });

  it("does not throw an unhandled rejection if the local sign-out itself fails", async () => {
    mockGetSession.mockResolvedValue({ data: { session: { access_token: "stale" } } } as never);
    mockSignOut.mockRejectedValue(new Error("storage unavailable"));
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(401, { detail: "nope" }));

    // Must reject with the ApiError, not with the sign-out's own error,
    // and must not raise an unhandled promise rejection in the process.
    await expect(getDashboardStats()).rejects.toBeInstanceOf(ApiError);
  });
});
