CurseDeck's first downloadable test release for Decky Loader.

- Install and update World of Warcraft addons through CurseForge, including required dependencies.
- Try the offline demo without an API key or a real WoW installation.
- Automatically check GitHub for new CurseDeck releases on Decky startup and every six hours.
- Install future releases from CurseDeck → Plugin updates, using Decky's confirmation dialog, checksum verification, and reload. No manual ZIP downloads after initial installation.
- Preserve your WoW setup, CurseForge key, and addon registry between plugin updates.

Download **CurseDeck.zip** below for the initial installation. In Decky settings, enable developer mode and install the ZIP. Open CurseDeck → Setup → Try offline demo to test without credentials.

This is an early test release. Frontend checks, packaging, backend tests, and offline integration tests pass; on-device Decky installation and live CurseForge downloads still need testing. CurseForge browsing/downloads require an approved API key. The updater uses a Decky installer bridge checked against the current Loader source; an unsupported Loader version displays an error instead of attempting a direct file replacement. Updates require Decky's confirmation rather than silent background installation.

`update.json` contains the version, pinned download URL, and SHA-256 checksum used by the in-app updater.
