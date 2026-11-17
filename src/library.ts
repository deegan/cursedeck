export type Installed = { id: number; name: string; version: string; update: string | null; error: string | null; missing: boolean; adopted?: boolean; blocked?: boolean; fileId?: number; download?: {fileName: string; page: string} };
export type Library = { addons: Installed[]; unmanaged: string[]; path?: string; matching?: {matched: number; unmatched: string[]; modified: string[]}; localAddons?: {folder: string; name: string; version: string | null; notes: string; error: string | null}[] };

// An install returns the plain listing; keep the last check's results for addons it did not change.
export function keepChecked(previous: Library, next: Library): Library {
  const before = new Map(previous.addons.map(a => [a.id, a]));
  return {...next, matching: previous.matching, addons: next.addons.map(addon => {
    const old = before.get(addon.id);
    return old && old.fileId === addon.fileId
      ? {...addon, update: old.update, error: old.error, blocked: old.blocked, download: old.download}
      : {...addon, blocked: old?.blocked};
  })};
}
