Keep your place in CurseDeck when Quick Access closes.

- Decky rebuilds the plugin panel each time Quick Access reopens, which sent CurseDeck back to My addons and discarded unsaved Setup choices. The selected tab, installation, edition, search and an entered API key now survive until Decky unloads the plugin.
- Loading the API key from a text file now works: the file picker closes Quick Access, and the key used to be lost when it did.
- Setup shows when a key has been entered but not yet saved.
- Fix "Could not reach CurseForge" and failed plugin update checks on SteamOS. Decky's bundled Python could not find the system's security certificates, so every secure connection was rejected. CurseDeck now uses the certificate bundle Decky ships, or the system's own.
- Connection errors now say whether the connection timed out, was missing, or could not be verified.
