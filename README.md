# CurseDeck

![CurseDeck banner](CurseDeck_banner.jpeg)

**World of Warcraft addons, right from Gaming Mode.**

CurseDeck brings addon management to your Steam Deck through [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader). Find your WoW installation, see what's installed, and connect to CurseForge to browse, install, and update addons without switching to Desktop Mode.

[Download CurseDeck](https://github.com/deegan/cursedeck/releases/latest) · [Release notes](https://github.com/deegan/cursedeck/releases) · [Report an issue](https://github.com/deegan/cursedeck/issues)

> **You need your own free CurseForge API key.** Create one at <https://console.curseforge.com/>; see [Create your API key](#create-your-api-key). Copy pasting from desktop-mode to game-mode does not always work, so the recommended procedure is to copy the API key and paste it into a .txt file in your Downloads/ or Documents/ folder. During setup you select "Load from text-file" when asked for the API key and select the file from the file browser..

## Features

- **Find your installation.** Detect WoW in Steam libraries, Proton prefixes, common game folders, and mounted SD cards—including installations made through Battle.net.
- **Choose your version.** Select Retail, Classic, Forever, or another detected installation from a dropdown. Use the folder browser for other locations.
- **See your addons.** View installed addon names, versions, and descriptions directly from your WoW folder, even offline.
- **Browse CurseForge.** Search for addons filtered to your selected WoW edition.
- **Install dependencies.** Required addon dependencies are included automatically.
- **Keep addons current.** Check for stable releases and update addons managed by CurseDeck individually or together.
- **Update CurseDeck in Gaming Mode.** Get notified about new plugin releases and install them through Decky's confirmation dialog.

## Install

You'll need Decky Loader and a World of Warcraft installation on your Steam Deck. Internal storage and SD cards are supported.

1. Download **[CurseDeck.zip](https://github.com/deegan/cursedeck/releases/latest/download/CurseDeck.zip)** onto your Steam Deck.
2. Open Decky's settings and enable developer mode.
3. Use Decky's **Install plugin from ZIP** option and select the downloaded file.
4. Open **CurseDeck** from the Decky panel.

## Set up CurseDeck

Open **CurseDeck → Setup** and work down the page:

1. **Find World of Warcraft.** CurseDeck searches the Deck and SD card when you open Setup. If your installation isn't found, select **Search for WoW installations** again, or **Browse for the WoW folder** and pick the SD card or World of Warcraft folder.
2. **Pick your version.** Choose the installation you play, such as Retail or Forever, from **WoW version**. The folder is shown beneath it.
3. **Add your CurseForge API key.** Select **Load key from a text file** and pick the file holding your key (see [Create your API key](#create-your-api-key)), or type it in. CurseDeck checks the key with CurseForge straight away and fills in the matching **CurseForge edition**. For Classic, choose the edition you play.
4. **First-time sync.** Select **Sync my addons**. CurseDeck saves your setup, recognises the addons you already have, and checks them for updates. Your addon files are not changed.

You can come back to Setup at any time to switch installations or replace your key, then sync again.

**My addons** shows the scanned folder and a compact list of addon names and versions. Select an addon to expand its description, folder, and other details. Available updates and issues are marked on the collapsed row. Use **Refresh installed addons** after making changes with another addon manager.

### Existing addons

Addons already present in your WoW folder show **Installed outside CurseDeck** in their expanded details. CurseDeck lists their names and versions and leaves their files in place.

**My addons → Check for updates** also recognises existing addons. CurseDeck fingerprints each folder the way the CurseForge app does and asks CurseForge which release it is. An addon that matches a release exactly is listed as **Recognised on CurseForge** and can be updated like one CurseDeck installed: updating replaces its folders with the new release. Nothing on disk changes until you choose to update. Folders that were edited or come from elsewhere do not match and are left alone.

Some authors only allow downloads through CurseForge's own app or website. For those addons, CurseDeck shows **Open download page** and **Install downloaded ZIP**: download the file from CurseForge, then choose it. CurseDeck installs it only if its size and checksums match the release CurseForge lists. If Steam's browser does not save the download, use a browser in Desktop Mode; the file can be anywhere on the Deck.

## Create your API key

CurseDeck uses your own personal CurseForge API key. It is free, and CurseDeck does not include one. This is easiest on a computer or in Desktop Mode:

1. Open <https://console.curseforge.com/> and sign in with a CurseForge account (create one if needed).
2. Open **API keys** in the console's menu and create or view your key.
3. Copy the whole key. It is a long line of text starting with `$2a$10$`.

Typing the key with the Deck's on-screen keyboard is error-prone, so save it in a text file instead: paste the key into a new file containing only the key, for example `curseforge-key.txt`, and copy the file to the Deck. Put it somewhere visible such as `Documents` or `Downloads`, since the file browser does not show hidden folders. Once setup is synced you can delete the file.

Your key is saved locally in Decky's plugin settings and is only sent to `api.curseforge.com`. Never share it.

Some authors disable third-party downloads for their addons. CurseDeck respects those settings: for those addons, download the file from CurseForge yourself and install it with **Install downloaded ZIP**.

## Install and update addons

Close WoW before installing or updating addons.

- **Find addons:** Search by name, browse the results, and select **Install**. CurseDeck also installs required dependencies.
- **My addons → Check for updates:** Look for newer stable releases of addons managed by CurseDeck.
- **Update / Update all:** Install an individual update or all available updates.
- **Repair / reinstall:** Expand a managed addon's details to restore its current release.

CurseDeck checks download integrity and stages addon files before replacing managed folders. Updates preserve your WoW `WTF` settings. Personal changes inside a managed addon's own folder are replaced during updates.

## Keep CurseDeck up to date

CurseDeck checks GitHub for new plugin releases when Decky loads and every six hours while Steam is running. You can disable automatic checks in **Plugin updates** or check manually whenever you like.

To update, open **Plugin updates**, select **Install CurseDeck [version]**, and confirm Decky's installation dialog. CurseDeck downloads and verifies the package before handing it to Decky for installation. The update screen retains the attempt status across reloads and confirms success when the new package version is loaded.

Plugin updates do not require a CurseForge API key. If an update does not complete, the latest release ZIP can also be installed through Decky's ZIP installer.

## Troubleshooting

**My WoW installation isn't listed.**

Check that the SD card or game drive is mounted. Use **Browse for the WoW folder** in Setup to select the card or WoW folder.

**My addons list is empty.**

Check the scanned path shown in **My addons** and make sure you selected the edition you play. Then select **Refresh installed addons**.

**CurseForge search or downloads aren't available.**

Complete Setup with your API key from <https://console.curseforge.com/> and the matching CurseForge edition. If CurseForge rejects the key, check that you copied all of it, starting with `$2a$10$`. Check your connection and any error shown in the panel.

**An addon is listed but has no Update button.**

Select **Check for updates** first. Addons that match a CurseForge release exactly become updatable; folders that were edited or come from elsewhere stay **Installed outside CurseDeck** and are left alone.

For other problems, [open an issue](https://github.com/deegan/cursedeck/issues) with your CurseDeck and Decky Loader versions, the steps you followed, and the error message. Never include your API key.

## Build from source

Requires Node.js/npm and Python 3.9 or newer.

```sh
npm ci
npm test
npm run test:frontend
npm run package
```

The installable package is written to `out/CurseDeck.zip`.

[GitHub Actions](https://github.com/deegan/cursedeck/actions/workflows/build.yml) runs the tests and produces downloadable build artifacts. Version tags publish release packages and their update manifests.

---

CurseDeck is an independent project and is not affiliated with Blizzard Entertainment, CurseForge, Overwolf, or Decky Loader.
