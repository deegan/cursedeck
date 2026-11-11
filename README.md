# CurseDeck

A first implementation of a Decky Loader plugin for installing and updating World of Warcraft addons from Gaming Mode. React/TypeScript provides the Decky panel; a Python standard-library backend handles CurseForge access and addon files.

**Status:** backend tests pass locally. The frontend has not been compiled or tested in Decky yet: the development sandbox cannot resolve npm's registry. Live API/download testing also requires an approved CurseForge API key. This is not yet a verified Steam Deck release.

## Features

- Search CurseForge with pagination, filtered to your selected WoW edition.
- Install stable addon releases and required dependencies.
- List managed addons, check for updates, update individually or update all, and repair missing files.
- Load WoW editions from CurseForge instead of hardcoding changing Classic versions.
- Configure a WoW edition folder in a Proton/Wine prefix, including a mounted SD card.
- Preserve unmanaged addons and all WTF settings.
- Verify download lengths and checksums; reject unsafe ZIP entries, symlinks, duplicate paths, oversized archives, and conflicting addon folders.
- Stage the whole dependency set before replacement and restore replaced folders if a normal filesystem operation fails.

## Requirements

- Decky Loader with the modern `@decky/api` plugin interface (API version 1).
- A WoW installation writable by Decky's normal plugin user. No root plugin flag is used.
- A CurseForge API key approved for third-party API use. [Apply through CurseForge](https://support.curseforge.com/support/solutions/articles/9000208346-about-the-curseforge-api-and-how-to-apply-for-a-key). A CurseForge website login alone does not supply an API key.
- Node.js/npm for building and Python 3.9+ for the backend/tests.

CurseForge may disallow third-party distribution for individual projects. CurseDeck respects those restrictions; it cannot replace the CurseForge app for every addon. The API key is sent in headers to the official API and trusted HTTPS ForgeCDN hosts, including download redirects. See the [API reference](https://docs.curseforge.com/rest-api/) and [CDN authentication announcement](https://blog.curseforge.com/introducing-api-key-authentication-for-curseforge-file-downloads/).

## Build and install

On a machine with internet access, run from this directory:

```sh
npm install
npm test
npm run package
```

The package command type-checks the frontend, builds it with Decky's Rollup preset, and creates `out/CurseDeck.zip`. Keep the generated `package-lock.json` for reproducible subsequent builds (`npm ci`). No installable ZIP is included until a real build succeeds.

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

Backend tests use isolated temporary WoW installations and mocked CurseForge responses, never a real game installation. Before release, validate on Decky: controller navigation, password entry, API-key failures, edition selection, real addon/dependency downloads, a second-version update, and SD-card paths. Packaging follows the [official Decky template](https://github.com/SteamDeckHomebrew/decky-plugin-template).

CurseDeck is an independent project, not affiliated with CurseForge, Overwolf, Blizzard, or Decky Loader.
