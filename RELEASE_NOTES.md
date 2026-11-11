View your real installed WoW addons without a CurseForge API key.

- Save a detected or manually entered WoW folder using **Save folder and scan addons**.
- List existing addons with their names, versions, notes, and folder names, read directly from local `.toc` files.
- Use **Refresh installed addons** to rescan after external changes.
- See the exact AddOns path being scanned and clearer empty-list guidance.
- Leave sample data with **Leave demo and find my addons**.
- Handle Interface/AddOns directory capitalization without creating an empty duplicate directory.

Upgrade through **CurseDeck → Plugin updates → Check for plugin update → Install**, then confirm Decky's dialog. Leave demo mode, choose your real WoW installation in Setup, and save the folder.

Local listing requires no API key or network connection. Online CurseForge search, downloads, and update checks still require a key and edition selection. Existing addons are labeled **Installed outside CurseDeck**; automatic update matching for them remains unimplemented.

All 48 Python tests, frontend updater tests, TypeScript checks, package build, and offline smoke test pass. Real Steam Deck operation and live CurseForge downloads still need validation.
