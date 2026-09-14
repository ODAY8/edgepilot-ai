import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { importWithReload } from "./lazyImport";

describe("importWithReload", () => {
  let reloadSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    sessionStorage.clear();
    reloadSpy = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...window.location, reload: reloadSpy },
    });
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it("resolves normally and clears any reload flag on success", async () => {
    const mod = { default: () => null };
    const result = await importWithReload(() => Promise.resolve(mod));

    expect(result).toBe(mod);
    expect(sessionStorage.getItem("edgepilot:chunk-reload-attempted")).toBeNull();
    expect(reloadSpy).not.toHaveBeenCalled();
  });

  it("reloads once on a failed dynamic import instead of surfacing a dead-end error", async () => {
    const factory = () => Promise.reject(new Error("Failed to fetch dynamically imported module"));

    // The retry path resolves via a never-settling promise (the real
    // reload replaces the page), so just confirm the recovery action
    // happened rather than awaiting the returned promise.
    void importWithReload(factory);
    await new Promise((r) => setTimeout(r, 0));

    expect(reloadSpy).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem("edgepilot:chunk-reload-attempted")).toBe("1");
  });

  it("gives up and throws the real error if the import still fails after a retry", async () => {
    sessionStorage.setItem("edgepilot:chunk-reload-attempted", "1");
    const error = new Error("Failed to fetch dynamically imported module");

    await expect(importWithReload(() => Promise.reject(error))).rejects.toThrow(
      "Failed to fetch dynamically imported module",
    );
    expect(reloadSpy).not.toHaveBeenCalled();
    expect(sessionStorage.getItem("edgepilot:chunk-reload-attempted")).toBeNull();
  });
});
