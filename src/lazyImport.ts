// A dynamic import() can fail purely at the network level -- the dev
// server restarting mid-session, or in production a tab left open across
// a new deploy trying to fetch a chunk hash that no longer exists. That's
// not a defect in the imported module; React.lazy() just never retries on
// its own, so the failure becomes a dead-end render error. Retrying once
// via a full reload recovers a fresh module graph; sessionStorage guards
// against looping forever if the failure is actually persistent.
const RELOAD_KEY = "edgepilot:chunk-reload-attempted";

export async function importWithReload<T>(factory: () => Promise<T>): Promise<T> {
  try {
    const mod = await factory();
    sessionStorage.removeItem(RELOAD_KEY);
    return mod;
  } catch (error) {
    if (sessionStorage.getItem(RELOAD_KEY)) {
      // Already retried once for this navigation attempt and it failed
      // again -- this isn't a transient blip, so surface the real error
      // instead of reloading forever.
      sessionStorage.removeItem(RELOAD_KEY);
      throw error;
    }
    sessionStorage.setItem(RELOAD_KEY, "1");
    window.location.reload();
    // The reload will replace this page before this promise would
    // otherwise need to settle.
    return new Promise<T>(() => {});
  }
}
