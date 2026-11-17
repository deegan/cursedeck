Update the addons you already have, and keep your place when Quick Access closes.

- **Check for updates** now recognises addons installed another way. CurseDeck fingerprints each addon folder like the CurseForge app does, matches it to its CurseForge release, and then offers updates for it. Nothing changes on disk until you update. Edited folders are not matched and are left alone.
- Addons whose authors only allow downloads through CurseForge's own app show their available update without an Update button.
- When one addon's release bundles a folder another managed addon also provides (Questie now includes QuestieTrace), installing it takes that folder over instead of failing. Folders CurseDeck does not manage are still never overwritten.
- The update check reports what it covered.

- Decky rebuilds the plugin panel each time Quick Access reopens, which sent CurseDeck back to My addons and discarded unsaved Setup choices. The selected tab, installation, edition, search and an entered API key now survive until Decky unloads the plugin.
- Loading the API key from a text file now works: the file picker closes Quick Access, and the key used to be lost when it did.
- Setup shows when a key has been entered but not yet saved.
- Fix "Could not reach CurseForge" and failed plugin update checks on SteamOS. Decky's bundled Python could not find the system's security certificates, so every secure connection was rejected. CurseDeck now uses the certificate bundle Decky ships, or the system's own.
- Connection errors now say whether the connection timed out, was missing, or could not be verified.
