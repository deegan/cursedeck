# CurseDeck

A first implementation of a Decky Loader plugin for installing and updating World of Warcraft addons from Gaming Mode. React/TypeScript provides the Decky panel; a Python standard-library backend handles CurseForge access and addon files.

**Status:** The frontend passes TypeScript checks and builds successfully, and an installable test ZIP can be generated with `npm run package`. The 23 backend, plugin integration, and packaging tests and the offline smoke test have passed. Testing in Decky on a Steam Deck and live CurseForge downloads with an approved API key remain outstanding.

## Features

- Search CurseForge with pagination, filtered to your selected WoW edition.
- Install stable addon releases and required dependencies.
- List managed addons, check for updates, update individually or update all, and repair missing files.
- Load WoW editions from CurseForge instead of hardcoding changing Classic versions.
- Configure a WoW edition folder in a Proton/Wine prefix, including a mounted SD card.
- Preserve unmanaged addons and all WTF settings.
- Verify download lengths and checksums; reject unsafe ZIP entries, symlinks, duplicate paths, oversized archives, and conflicting addon folders.
- Stage the whole dependency set before replacement and restore replaced folders if a normal filesystem operation fails.

## Try it without an API key

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

## Requirements

- Decky Loader with the modern `@decky/api` plugin interface (API version 1).
- A WoW installation writable by Decky's normal plugin user. No root plugin flag is used.
- A CurseForge API key approved for third-party API use. [Apply through CurseForge](https://support.curseforge.com/support/solutions/articles/9000208346-about-the-curseforge-api-and-how-to-apply-for-a-key). A CurseForge website login alone does not supply an API key.
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

1. In **Setup**, enter the absolute path to the edition folder containing `Wow.exe` or `WowClassic.exe`, not the Battle.net launcher or parent `World of Warcraft` folder. Example: `/home/deck/Games/battlenet/drive_c/Program Files (x86)/World of Warcraft/_retail_`. Your Proton prefix may use a different location.
2. Enter your API key and select **Load WoW editions**.
3. Select the edition matching that folder and **Save setup**. CurseDeck cannot infer the edition from the executable; verify the selection yourself.
4. Close WoW, then use **Find addons** to install addons.
5. Use **My addons → Check for updates**, then **Update** or **Update all**.

The saved API key is kept in Decky's plugin settings directory in a mode-0600 JSON file. It is never returned to the frontend after saving or bundled in the ZIP. Blank key input preserves the existing key. Configuration switches one active installation at a time; each installation keeps its own managed addon registry at `Interface/AddOns/.cursedeck.json`.

## Existing addons and limitations

Existing addon folders are displayed as unmanaged and are never automatically overwritten. To adopt one, first back it up outside `Interface/AddOns`, then install its CurseForge project through CurseDeck. Leave your `WTF` folder in place. Automatic fingerprint-based adoption, uninstall, release channels, scheduled updates, and installation discovery are not implemented.

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
