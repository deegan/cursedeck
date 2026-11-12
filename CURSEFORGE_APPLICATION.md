# CurseDeck — API access application

**Subject: API access request — CurseDeck, World of Warcraft addon management in Steam Deck Gaming Mode**

Hello CurseForge team,

I'm developing CurseDeck, an independent Decky Loader plugin that lets World of Warcraft players manage their addons from Steam Deck Gaming Mode. I'd like to request approval for this use case and limited API access to validate the integration before a public launch of its online features.

The problem is practical: managing a WoW installation on a handheld can involve switching to Desktop Mode, navigating Proton folders, finding an installation on an SD card, and using interfaces designed around a mouse and keyboard. CurseDeck brings those tasks into a controller-accessible panel alongside the player's game.

Its proposed CurseForge integration would let players search for addons for their WoW edition, install them with required dependencies, and check for and install stable updates. These functions overlap with addon management in the CurseForge app. I'm asking for explicit approval for that functionality in this Steam Deck experience.

CurseDeck adds device-specific functionality around the API:

- Detection of WoW installations in Steam libraries, Proton prefixes, and mounted SD cards, including installations made through Battle.net.
- An installation dropdown that avoids requiring players to know internal folder names or Steam shortcut IDs.
- Local inspection of existing addon names and versions, available without API access.
- Compact, expandable addon lists within Decky, with install and update controls designed for handheld use.
- Staged installation, archive and checksum validation, and rollback handling to protect the player's existing installation.

For CurseForge, the potential benefit is making its catalogue easier to use in a specific handheld workflow while keeping discovery and downloads connected to CurseForge. I see an opportunity to help players maintain their addons and discover authors through an approved integration; I don't yet have usage or revenue data to quantify that benefit.

Your [application guidance](https://support.curseforge.com/support/solutions/articles/9000208346-about-the-curseforge-api-and-how-to-apply-for-a-key) identifies author earnings, infrastructure load, and author consent as review priorities. Here is the current design and what I propose for each.

**Author consent and earnings**

The installer checks project distribution settings and refuses installation when third-party distribution is explicitly disabled, including for required dependencies. It uses download URLs supplied by the API and stops when access is denied or a download is unavailable. It has no website scraping, guessed download URLs, alternative mirrors, or rehosting service.

I would like your guidance on download accounting and any author-revenue requirements for this integration. I cannot assume that direct CDN downloads alone satisfy those requirements. Author credits and links to original CurseForge project pages are planned additions to the interface, and I would welcome your requirements for their presentation. The current prototype has no payments or advertising; any required commercial arrangement would need to be agreed before launch.

**API usage and infrastructure**

The intended API scope is WoW edition metadata, addon search, project and file metadata, dependency resolution, and download URLs. Search results are paginated. Addon update checks and downloads are initiated by the user; the plugin does not periodically crawl the CurseForge catalogue. Plugin self-update checks use GitHub separately.

The current release-selection implementation can make too many requests when inspecting long file histories. Reducing those requests and improving batch handling of rate-limit responses are outstanding work before public online use. I propose beginning with a limited evaluation quota that you specify, measuring actual request and download volume, and agreeing suitable limits before expanding access. I do not yet have a reliable active-user or traffic forecast.

**Approval and architecture questions**

After reviewing the [third-party API terms](https://support.curseforge.com/support/solutions/articles/9000207405-curse-forge-3rd-party-api-terms-and-conditions), I would appreciate written clarification on:

1. Whether this WoW addon manager is an approved use under the competing-product restriction in §3.1, and whether a separate agreement is needed.
2. The supported authentication model for a downloadable plugin under §2.2. The prototype accepts a user-supplied key; I am not proposing to distribute a shared developer secret in its source or release package.
3. Whether you support an approved user sign-in or delegated authorization flow for third-party WoW addon managers, allowing players to connect their own CurseForge accounts without handling developer API keys. This would simplify setup on a handheld. If available, what application credentials, permissions, and approval would CurseDeck still require? I am asking about a supported integration, not assuming that a website login grants API access.
4. Permission under §3.1 to retain a local installation record containing project IDs, installed file IDs, names, versions, and folder ownership, plus temporary staging files during installation. This record supports update detection and safe file replacement.
5. Any required attribution, branding, revenue arrangements, usage reporting, quotas, or restrictions specific to World of Warcraft access.

**Readiness and review access**

The local installation-discovery and addon-listing features have been exercised on a Steam Deck. Online workflows have implementation and offline test coverage, but live CurseForge integration has not yet been validated. Credential handling also needs tightening so API keys are sent only to the API host and are not forwarded to download hosts or across redirects. I would complete that work before testing with a real credential.

Development builds were previously published on GitHub. I have now made the repository private while clarifying approval and the distribution model. The repository is [deegan/cursedeck](https://github.com/deegan/cursedeck); it will require reviewer access, which I can arrange on request. I can also provide screenshots or a demonstration of the local and offline-demo workflows.

Would you be willing to review CurseDeck for a limited evaluation and advise on the conditions for an approved public integration? I would be happy to discuss changes to the design, authentication model, or scope that would make this useful to Steam Deck players while meeting your requirements.

Thank you for considering the project.

deegan  
CurseDeck developer
