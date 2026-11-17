Keep your CurseForge API key away from download servers, and load it from a file instead of typing it.

- The API key is now sent only to api.curseforge.com. Earlier builds also sent it to CurseForge's download CDN when fetching addon archives.
- The key is removed from any request that is redirected away from the API host.
- New in Setup: **Load API key from a text file**. Browse to a text file containing only your key instead of entering it with the on-screen keyboard.

Local addon listing still works without an API key. Online search, addon downloads, and update checks require a CurseForge API key.
