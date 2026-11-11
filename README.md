# CurseDeck

A first implementation of a Decky Loader plugin for installing and updating World of Warcraft addons from Gaming Mode. React/TypeScript provides the Decky panel; a Python standard-library backend handles CurseForge access and addon files.

**Status:** The frontend passes TypeScript checks and builds successfully, and an installable test ZIP can be generated with `npm run package`. The 48 backend, local addon, discovery, plugin integration, packaging, and release updater tests and the offline smoke test have passed. Testing in Decky on a Steam Deck and live CurseForge downloads with an approved API key remain outstanding.

## Download and plugin updates

Download **CurseDeck.zip** from the [latest GitHub release](https://github.com/deegan/cursedeck/releases/latest) for your first installation. Future releases can be installed from **CurseDeck → Plugin updates** in Gaming Mode.

CurseDeck automatically checks GitHub when Decky loads and every six hours while Steam is running. When a newer stable version is available, it shows a notification. Select **Install CurseDeck [version]** and confirm Decky's installation dialog; Decky downloads the release ZIP, verifies its SHA-256 checksum, and reloads the plugin. Automatic checking can be disabled in **Plugin updates**. You can also check manually there.

This updates the CurseDeck plugin itself; **My addons → Update all** updates your WoW addons. Release checks require internet access but do not require a CurseForge API key. Plugin updates preserve your stored key, setup, update preferences, and WoW addon registry. Unattended installation is not enabled: Decky asks you to confirm each plugin update. The installer bridge depends on Decky's Loader interface; unsupported Loader versions display an error requesting a Decky update. On-device installation/reload remains to be validated.

## Features

- Search CurseForge with pagination, filtered to your selected WoW edition.
- Install stable addon releases and required dependencies.
- List existing addons from their local manifests without an API key.
- List managed addons, check for updates, update individually or update all, and repair missing files.
- Load WoW editions from CurseForge instead of hardcoding changing Classic versions.
- Detect WoW installations in Steam game folders and Proton prefixes, including Steam libraries on SD cards and Flatpak Steam.
- Select a detected installation or enter a custom WoW edition folder.
- Preserve unmanaged addons and all WTF settings.
- Verify download lengths and checksums; reject unsafe ZIP entries, symlinks, duplicate paths, oversized archives, and conflicting addon folders.
- Stage the whole dependency set before replacement and restore replaced folders if a normal filesystem operation fails.

## View your addons without an API key

In **Setup**, choose Retail, Classic, or another detected edition from the **WoW installation** dropdown and choose **Show my addons**. **My addons** reads names, versions, and notes from the installed `.toc` manifests. Use **Refresh installed addons** after installing or removing addons outside CurseDeck. The scanned directory is shown so you can check that you selected the correct WoW edition. Existing addons are labeled **Installed outside CurseDeck**; automatic update matching for them is not implemented.

If you see Quest Compass or Shared Library marked demo, select **Leave demo and find my addons**, then choose your real installation. Local listing needs neither a CurseForge key nor internet access. Online search, downloads, and version checks require an API key and a saved CurseForge edition.

## Optional offline demo

After building and installing the plugin, open **Setup → Try offline demo**. No API key or real WoW installation is needed.

The demo starts with Quest Compass and its required Shared Library installed at version 1.0. Use **Check for updates** and **Update all** to install version 2.0, or search for Raid Notes and install it. Sample downloads pass through the same checksum, extraction, dependency, and replacement code used for real addons. The panel always shows an offline-demo banner.

All demo files live in an isolated temporary directory. **Setup → Leave offline demo** deletes them and restores your saved real setup. Demo mode does not persist across plugin restarts. Re-enter it to start fresh. It never contacts CurseForge or modifies your real WoW installation.

You can exercise the same workflow from a terminal today, without building the frontend:

```sh
python3 scripts/demo_smoke.py
```

## GitHub test builds

The **Build CurseDeck** workflow runs on pushes, pull requests, and manual dispatch. It tests the backend on Python 3.9 and 3.13, type-checks and builds the frontend, and uploads **CurseDeck-test-build** containing `CurseDeck.zip` and the committed npm lockfile. No API key or repository secret is needed. Check [GitHub Actions](https://github.com/deegan/cursedeck/actions/workflows/build.yml) for the latest build results.

Download the artifact from a successful Actions run and extract it to obtain the installable ZIP. Builds use `npm ci` with the committed `package-lock.json` to pin dependency versions.

To publish a new version, update `package.json` and `package-lock.json`, edit `RELEASE_NOTES.md`, commit the changes, and push a matching `vMAJOR.MINOR.PATCH` tag. After the backend tests and package build pass, the workflow creates the GitHub release with `CurseDeck.zip` and `update.json`. The manifest contains the tagged ZIP URL and its SHA-256 checksum. Release publication uses GitHub Actions' repository token; no personal access token is required.

## Requirements

- Decky Loader with the modern `@decky/api` plugin interface (API version 1).
- A WoW installation writable by Decky's normal plugin user. No root plugin flag is used.
- For online search, downloads, and update checks: a CurseForge API key approved for third-party API use. [Apply through CurseForge](https://support.curseforge.com/support/solutions/articles/9000208346-about-the-curseforge-api-and-how-to-apply-for-a-key). A CurseForge website login alone does not supply an API key.
- Node.js/npm for building and Python 3.9+ for the backend/tests.

CurseForge may disallow third-party distribution for individual projects. CurseDeck respects those restrictions; it cannot replace the CurseForge app for every addon. The API key is sent in headers to the official API and trusted HTTPS ForgeCDN hosts, including download redirects. See the [API reference](https://docs.curseforge.com/rest-api/) and [CDN authentication announcement](https://blog.curseforge.com/introducing-api-key-authentication-for-curseforge-file-downloads/).

## Build and install

On a machine with internet access, run from this directory:

```sh
npm ci
npm test
npm run package
```

The package command type-checks the frontend, builds it with Decky's Rollup preset, and creates `out/CurseDeck.zip`. The committed `package-lock.json` pins dependencies for reproducible installs. Build output is excluded from Git; build locally or download a successful GitHub Actions artifact.

Transfer the ZIP to your Steam Deck. Enable developer mode in Decky's settings and use its ZIP installation option to install it. Open CurseDeck in Decky's panel.

1. **Setup** scans Steam libraries automatically on first setup. Use **Find WoW installations** to scan again and select a result in the **WoW installation** dropdown. If no result matches, enable **Use a custom location** and enter the absolute path to the edition folder containing `Wow.exe` or `WowClassic.exe`, not the Battle.net launcher or parent `World of Warcraft` folder. Example: `/home/deck/Games/battlenet/drive_c/Program Files (x86)/World of Warcraft/_retail_`. Your Proton prefix may use a different location.
2. Select **Show my addons** to view your installed addons immediately, without an API key.
3. For online features, return to **Setup**, enter your API key, select **Load WoW editions**, choose the matching edition, and **Save setup**. CurseDeck cannot infer the edition from the executable; verify the selection yourself.
4. Close WoW, then use **Find addons** to install addons.
5. Use **My addons → Check for updates**, then **Update** or **Update all**.

The saved API key is kept in Decky's plugin settings directory in a mode-0600 JSON file. It is never returned to the frontend after saving or bundled in the ZIP. Blank key input preserves the existing key. Configuration switches one active installation at a time; each installation keeps its own managed addon registry at `Interface/AddOns/.cursedeck.json`.

## Installation discovery

Discovery reads Steam's `libraryfolders.vdf`, then searches each library's `steamapps/common` and `steamapps/compatdata/<id>/pfx/drive_c` folders for `Wow.exe` or `WowClassic.exe`. It supports native and Flatpak Steam locations, additional registered libraries (including SD cards), multiple WoW editions, and arbitrary Proton IDs. Duplicate paths are collapsed. The dropdown uses readable edition names; duplicate installations of the same edition are numbered and show the selected location beneath the dropdown. A single detected installation is preselected. Saved locations remain selectable even if a scan does not find them. Manual path input is hidden behind **Use a custom location**. Selecting an installation resets the edition selection so you can explicitly choose the matching CurseForge edition before saving.

The scan is read-only and does not require an API key. It skips large game-data and system folders and uses depth, directory-count, and time limits to keep setup responsive. Partial scans report a warning. Custom installations outside Steam libraries, inaccessible drives, or unusually deep folder layouts may need the manual path field. A folder name alone is insufficient: a supported WoW executable must be present.

## Existing addons and limitations

Existing addons show their names and versions from local `.toc` manifests and are labeled **Installed outside CurseDeck**. They are never automatically overwritten. To adopt one, first back it up outside `Interface/AddOns`, then install its CurseForge project through CurseDeck. Leave your `WTF` folder in place. Automatic fingerprint-based adoption, uninstall, release channels, and scheduled addon updates are not implemented.

Only stable releases for the selected edition are installed; compatibility is based on CurseForge edition metadata, not an exact installed WoW patch. Archives must contain top-level addon folders with `.toc` files. Unusual archive layouts are rejected. An update replaces each managed folder, including locally edited addon code; back up personal edits separately.

Rollback covers caught errors during replacement. It is not power-loss/crash recovery, and a force-terminated install can leave temporary backup folders under AddOns. Keep your own backup before first use. Do not run other addon managers concurrently. All operations within this plugin are serialized.

## Development and validation

```sh
python3 -m unittest discover -s tests -v
npm run typecheck
npm run build
```

Backend and plugin integration tests use isolated temporary WoW installations and mocked CurseForge responses, never a real game installation. In this restricted development sandbox, async integration tests were run with selector polling because Unix socket sends (including asyncio thread wakeups) are denied. Production code and the CI test command are unchanged. Before release, validate on Decky: controller navigation, password entry, API-key failures, edition selection, real addon/dependency downloads, a second-version update, and SD-card paths. Packaging follows the [official Decky template](https://github.com/SteamDeckHomebrew/decky-plugin-template).

CurseDeck is an independent project, not affiliated with CurseForge, Overwolf, Blizzard, or Decky Loader.
