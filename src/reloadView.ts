type DeckyPlugin = { name: string; content?: unknown };
type DeckyState = {
  publicState(): { activePlugin?: DeckyPlugin | null; plugins?: DeckyPlugin[] };
  setActivePlugin(name: string): void;
};
export type DeckyLoader = { deckyState?: DeckyState };

// After an update Decky imports the new bundle, but a CurseDeck page that is already open keeps
// rendering the previous version's plugin object until the player leaves it. Once Decky has
// registered this copy, point that open page at it. Returns a function that stops waiting.
export function showLoadedVersion(content: unknown, loader?: DeckyLoader, attempts = 40, delay = 250): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let left = attempts;
  const step = () => {
    timer = undefined;
    try {
      const state = loader?.deckyState;
      if (!state || typeof state.publicState !== 'function' || typeof state.setActivePlugin !== 'function') return;
      const { activePlugin, plugins } = state.publicState();
      if (plugins?.some(p => p.name === 'CurseDeck' && p.content === content)) {
        if (activePlugin?.name === 'CurseDeck' && activePlugin.content !== content) state.setActivePlugin('CurseDeck');
        return;
      }
    } catch {
      return; // Decky internals changed; leaving the page and reopening still loads the new version.
    }
    if (--left > 0) timer = setTimeout(step, delay);
  };
  step();
  return () => { if (timer !== undefined) clearTimeout(timer); left = 0; };
}

export function deckyLoader(): DeckyLoader | undefined {
  return (window as unknown as {DeckyPluginLoader?: DeckyLoader}).DeckyPluginLoader;
}
