import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ErrorBoundary from "./ErrorBoundary";

function Bomb(): never {
  throw new Error("Simulated chart crash");
}

describe("ErrorBoundary", () => {
  let reloadSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // Swallow React's expected "the above error occurred in..." dev log
    // noise for this test so failures are easy to spot.
    vi.spyOn(console, "error").mockImplementation(() => {});
    reloadSpy = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...window.location, reload: reloadSpy },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders children normally when nothing throws", () => {
    render(
      <ErrorBoundary>
        <p>All good</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText("All good")).toBeInTheDocument();
  });

  it("catches a render error and shows a scoped fallback instead of a blank page", () => {
    render(
      <div>
        <p>Sidebar placeholder (should stay visible)</p>
        <ErrorBoundary>
          <Bomb />
        </ErrorBoundary>
      </div>,
    );

    expect(screen.getByText("Sidebar placeholder (should stay visible)")).toBeInTheDocument();
    expect(screen.getByText("This page failed to load.")).toBeInTheDocument();
    expect(screen.getByText("Simulated chart crash")).toBeInTheDocument();
  });

  it("offers a reload action from the fallback", async () => {
    const user = userEvent.setup();
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );

    await user.click(screen.getByRole("button", { name: /reload/i }));
    expect(reloadSpy).toHaveBeenCalled();
  });
});
