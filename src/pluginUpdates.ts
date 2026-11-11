export type PluginUpdate = {
  current: string; available: boolean; version: string | null;
  artifact: string | null; sha256: string | null; checked: boolean; automaticChecks: boolean;
};
type InstallerBridge = { call: (route: string, ...args: unknown[]) => Promise<unknown> };

export async function requestPluginUpdate(update: PluginUpdate, bridge?: InstallerBridge): Promise<void> {
  if (!bridge || typeof bridge.call !== 'function') {
    throw new Error('This Decky version does not expose the update installer. Update Decky Loader first.');
  }
  if (!update.available || !update.version || !/^\d+\.\d+\.\d+$/.test(update.version)
      || update.artifact !== `https://github.com/deegan/cursedeck/releases/download/v${update.version}/CurseDeck.zip`
      || !update.sha256 || !/^[a-f0-9]{64}$/.test(update.sha256)) {
    throw new Error('Check for a valid CurseDeck release before updating.');
  }
  // Decky's installer displays its confirmation prompt, verifies the hash and reloads the plugin.
  await bridge.call('utilities/install_plugin', update.artifact, 'CurseDeck', update.version, update.sha256, 2);
}

export function deckyInstallerBridge(): InstallerBridge | undefined {
  return (window as unknown as {DeckyBackend?: InstallerBridge}).DeckyBackend;
}
