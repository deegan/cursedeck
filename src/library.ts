type ReleaseDownload = { fileName: string; page: string; authorRelease?: boolean; localRelease?: boolean };
export type Installed = { id: number; name: string; logo?: string; version: string; update: string | null; error: string | null; missing: boolean; adopted?: boolean; blocked?: boolean; fileId?: number; download?: ReleaseDownload };
export type Library = { addons: Installed[]; unmanaged: string[]; path?: string; matching?: {matched: number; unmatched: string[]; modified: string[]}; localAddons?: {folder: string; name: string; version: string | null; notes: string; error: string | null}[] };

export function canUpdate(addon: Installed): boolean {
  return !!addon.update;
}

// A local refresh or install returns a plain listing. Keep checked results for unchanged releases.
export function keepChecked(previous: Library, next: Library): Library {
  if (previous.path !== next.path || next.matching) return next;
  const before = new Map(previous.addons.map(a => [a.id, a]));
  return {...next, matching: previous.matching, addons: next.addons.map(addon => {
    const old = before.get(addon.id);
    return old && old.fileId === addon.fileId
      ? {...addon, update: old.update, error: old.error, blocked: old.blocked, download: old.download}
      : {...addon, blocked: old?.blocked};
  })};
}

export function syncSummary(checked: Library): string {
  const found = checked.addons.filter(a => a.update).length;
  const failed = checked.addons.filter(a => a.error).length;
  const outside = checked.localAddons?.length ?? checked.unmanaged.length;
  const matched = checked.matching?.matched ?? 0;
  const parts = [];
  if (matched) parts.push(`Recognised ${matched} addon(s) on CurseForge.`);
  let outcome = failed ? 'No updates found' : 'Everything checked is up to date';
  if (found) outcome = `${found} update${found === 1 ? '' : 's'} available`;
  if (!checked.addons.length) parts.push('No addons could be checked.');
  else parts.push(`${outcome} (${checked.addons.length} checked${failed ? `, ${failed} need attention` : ''}).`);
  if (outside) parts.push(`${outside} folder(s) were not recognised and cannot be updated here.`);
  return parts.join(' ');
}
