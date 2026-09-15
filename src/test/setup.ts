import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement IntersectionObserver; framer-motion's viewport
// features (used by the Landing page) need at least a no-op stub to avoid
// crashing when those components mount in tests.
if (typeof globalThis.IntersectionObserver === "undefined") {
  class MockIntersectionObserver {
    readonly root: Element | Document | null = null;
    readonly rootMargin: string = "";
    readonly thresholds: ReadonlyArray<number> = [];
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords(): IntersectionObserverEntry[] {
      return [];
    }
  }
  globalThis.IntersectionObserver = MockIntersectionObserver as unknown as typeof IntersectionObserver;
}
