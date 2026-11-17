export type Installation = {path: string; label: string; source: string};

export function editionLabel(path: string): string {
  const folder = path.replace(/\/+$/, '').split('/').pop() ?? '';
  const known: Record<string, string> = {
    _retail_: 'Retail', _classic_: 'Classic', _classic_era_: 'Classic Era',
    _ptr_: 'PTR', _beta_: 'Beta',
  };
  return known[folder] ?? (folder.replace(/^_+|_+$/g, '').replace(/_/g, ' ')
    .replace(/\b\w/g, letter => letter.toUpperCase()) || 'World of Warcraft');
}

export function installationOptions(installations: Installation[], savedPath: string) {
  const items = [...installations];
  if (savedPath && !items.some(item => item.path === savedPath)) {
    items.push({path:savedPath, label:'', source:'Saved location'});
  }
  const counts = new Map<string, number>();
  for (const item of items) {
    const label = editionLabel(item.path);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  const positions = new Map<string, number>();
  return items.map(item => {
    const edition = editionLabel(item.path);
    const position = (positions.get(edition) ?? 0) + 1;
    positions.set(edition, position);
    return {data:item.path, label:edition + ((counts.get(edition) ?? 0) > 1 ? ` (${position})` : '')
      + (item.source === 'Saved location' ? ' · saved location' : '')};
  });
}

// The CurseForge edition for an installation folder, or 0 when it is not certain.
// _classic_ follows Blizzard's current progression realm, so the player picks that one.
export function editionFor(path: string, editions: {id: number; name: string}[]): number {
  const folder = (path.replace(/\/+$/, '').split('/').pop() ?? '').toLowerCase();
  const names: Record<string, RegExp> = {
    _retail_: /^wow retail$/i, _classic_era_: /^wow classic$/i, _forever_: /^wow forever$/i,
  };
  const pattern = names[folder];
  const matches = pattern ? editions.filter(edition => pattern.test(edition.name.trim())) : [];
  return matches.length === 1 ? matches[0].id : 0;
}
