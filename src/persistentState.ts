import { useEffect, useState } from 'react';

// Decky unmounts the plugin panel whenever Quick Access closes, including while
// the file picker is open. Module state lives as long as the plugin is loaded,
// and listeners keep a remounted panel in sync with replies that arrive late.
const store = new Map<string, unknown>();
const listeners = new Map<string, Set<(value: unknown) => void>>();

export function remembered(name: string): boolean {
  return store.has(name);
}

export function forgetAll(): void {
  store.clear();
}

export function usePersistentState<T>(name: string, initial: T): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => (store.has(name) ? store.get(name) as T : initial));
  useEffect(() => {
    const listener = (next: unknown) => setValue(next as T);
    const set = listeners.get(name) ?? new Set();
    set.add(listener);
    listeners.set(name, set);
    return () => { set.delete(listener); };
  }, [name]);
  return [value, (next: T) => {
    store.set(name, next);
    listeners.get(name)?.forEach(listener => listener(next));
  }];
}
