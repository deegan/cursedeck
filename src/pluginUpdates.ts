export type PluginUpdate = {
  installArtifact?: string;
  lastAttempt?: {target: string; status: string; message: string} | null;
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
  if (!update.installArtifact?.startsWith('file:///') ||
      !update.installArtifact.endsWith(`/update-cache/${update.version}-${update.sha256}/CurseDeck.zip`) ||
      update.installArtifact.split('/').includes('..')) {
    throw new Error('Download and verify the update before asking Decky to install it.');
  }
  // Decky's installer displays its confirmation prompt, verifies the hash and reloads the plugin.
  const result = await bridge.call('utilities/install_plugin', update.installArtifact, 'CurseDeck', update.version, update.sha256, 2);
  if (result === false || (result && typeof result === 'object' && 'success' in result && result.success === false)) {
    throw new Error('Decky rejected the update request. Check the Decky Loader log for details.');
  }
}

export function deckyInstallerBridge(): InstallerBridge | undefined {
  return (window as unknown as {DeckyBackend?: InstallerBridge}).DeckyBackend;
}
