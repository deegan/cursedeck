Find Battle.net's WoW installation directly on an SD card, and improve plugin-update handling.

- Scan mounted SD cards even when WoW is outside a registered Steam library.
- Scan common Games and Wine folders, and follow relocated Proton prefixes.
- Use **Browse SD card or game folder** to choose the card or World of Warcraft folder; editions appear in the dropdown without typing.
- Show how many directories discovery checked.
- Download and verify plugin updates before handing Decky a local ZIP. Validate SHA-256, archive paths, plugin identity, required files, and package version first.
- Preserve update attempt status through reloads. A GUI reload alone is not reported as a successful update.

If your existing updater only reloads the GUI, install **CurseDeck.zip** manually once to obtain this revised updater. Then test a subsequent update in Gaming Mode. The original device-side failure has not been reproduced locally; this release changes the download handoff and adds persistent failure visibility rather than claiming a confirmed root-cause fix.

After installing, open **Setup → Find WoW installations**. If the dropdown is still empty, select **Browse SD card or game folder**, choose the mounted card or WoW folder, select the detected edition, and press **Show my addons**. Local scanning and listing do not require an API key.

All 55 Python tests, frontend tests, type checks, and packaging pass. Steam Deck installation/reload and live CurseForge downloads remain to be validated on-device.
