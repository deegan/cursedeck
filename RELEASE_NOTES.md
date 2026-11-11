Find your WoW installation directly from CurseDeck's Setup screen.

- Automatically scan on first setup, or select **Find WoW installations** to scan again.
- Search Steam game folders and all numbered Proton prefixes without relying on a fixed Steam ID.
- Read Steam's library list to include SD cards and other registered libraries; support native and Flatpak Steam.
- Display every detected WoW edition with its full path, and collapse duplicate paths.
- Confirm installations using `Wow.exe` or `WowClassic.exe`; leave the filesystem unchanged during discovery.
- Keep manual path entry for custom locations, and report incomplete scans.

Upgrade from v0.2.0 through **CurseDeck → Plugin updates → Check for plugin update → Install**, then confirm Decky's dialog. For a first installation, download **CurseDeck.zip** below.

The frontend build, updater bridge tests, 39 Python tests, and offline smoke test pass. Tests cover arbitrary Proton IDs, SD-card libraries, Flatpak paths, multiple editions, duplicate symlinks, unreadable folders, and scan limits. Steam Deck hardware testing and live CurseForge downloads remain outstanding.
