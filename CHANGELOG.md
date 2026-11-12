# Changelog

## 0.1.6

- **The harness panel works in remote (SSH) windows.** The webview's browser lives on your machine while the harness and its embed proxy live on the remote host, so the panel used to dial *your* loopback address, find nobody home, and sit there in eloquent black. Local and WSL windows only ever worked because WSL forwards loopback by accident of architecture. The panel (and the app-window, built-in-browser, and external-browser doors) now aim at the address the editor itself forwards for the proxy, and the embed proxy accepts that forwarded origin as the panel's own — every cross-site drive-by still gets the same 403 it always got.

## 0.1.5

(Honest history: this content was briefly packaged as 0.1.4 during the same day's work; 0.1.4 never reached the Marketplace, so the number moved instead of the history.)

Linux grew up from "should work" to "did work", and the walkthrough found a prerequisite nobody had named.

- **The install procedure is verified end to end on Linux.** On a real Ubuntu: the prerequisite probes, the pinned dsh download through npm, core staging, profile creation, the adapter install through pnpm, the harness booting and announcing its loopback address, and the orphan sweep. The README now says Windows and Linux are both verified.
- **The setup check now names pnpm before anything downloads.** The harness installs its plugins with pnpm on every platform, and npm does not ship pnpm — so a machine without it used to watch the multi-minute runtime install complete and *then* die at the plugin step with an exit code and a log path. Now one line appears up front with the one-word fix, and a **Copy: npm install -g pnpm** button puts the command in your clipboard: the bridge asks, you install. It will never install tools on your machine by itself. This wall was platform-neutral; Windows machines without pnpm hit the identical dead end, and they get the same honest sentence now. When several prerequisites are missing, every one gets its own fix instead of only the first.
- **A security guard stopped guessing about filesystems.** The uninstall guard that refuses to recursively delete directories outside the bridge's own storage folded every path to lowercase because NTFS answers wrong-case paths with the same directory. On a case-sensitive filesystem that made a look-alike sibling with different capitalization read as *inside* the boundary. Case folding now happens only where the filesystem actually ignores case.

## 0.1.3

The full lifecycle is now commands, not folklore. Every verb a harness needs has a name in the palette, and each one hides itself when it would lie:

- **New: "Install or Update Harness…"** — pick the certified version, `latest` (clearly labeled experimental), or an exact pin, or "Repair … from scratch". It installs without ever starting the harness, runs behind the same cross-window start lock as Start, and a running harness converges through the normal drained restart instead of a second path. Repair clears only the completion stamps — the npm runtime redownloads, the core restages, your sessions and settings stay.
- **New: "Uninstall Harness"** — stops first (with an honest in-flight warning), confirms with what is about to die (runtime, profile, sessions, undelivered usage records), deletes the one `dsh-home` directory plus the legacy version-keyed ones, and reports the bytes freed. The bridge itself stays; the first-run offer comes back with a reinstall.
- **New: "Open Bridge Settings"** — the gear, reachable without a mouse menu.
- **Start got honest, not busy.** Its install behavior stays (a first Start still sets everything up), but the palette now knows what is installed: Uninstall appears exactly when there is a harness to remove, and Install/Update whenever the companion extension is present.
- **Named for the product, not one door.** The extension is now "DeepSeek Harness Bridge — run on your own models": vLLM-Copilot is the first-class, usage-accounted source of models — and a hard requirement the Marketplace page and README now say out loud — but the harness stays plain dsh: providers a user declares inside dsh (its pi-ai adapter, shipped enabled and empty by design) appear in the same picker beside vLLM-Copilot's. The README FAQ documents the verified recipe and its one boundary: extra doors are honest, but only registry traffic reaches your token totals.
- **The id became the name.** The extension is now `system-sciences.dsh-bridge` (was `dsh-vllm-bridge`): a publish rehearsal returned 404 for the old id — nothing had ever shipped under it, so this was the last moment a rename was free. Alpha testers on an older build: uninstall the old extension, install the new one, and move your `dsh-home` folder from the old storage directory to the new to keep your sessions. The internal dsh plugin keeps its name — inside the harness it honestly *is* the vLLM bridge.
- **The two truths lead the page.** Alpha status, and the fact that every server, model, and mode is configured in vLLM-Copilot (never in this bridge), now open the Marketplace description and the README's first screen — so nobody discovers the dependency after installing, or hunts for model settings here.
- **Security review before going public.** A full source and history review shaped this alpha: the embed proxy now refuses any browser request that admits it came from another site (drive-by pages can no longer ring the keyboard bridge or ride the harness session past its SameSite defense); the harness UI token no longer lands in the plaintext served-url history; token-carrying files are written owner-only on POSIX; harness URLs are trusted only on loopback, so no build can aim the panel at a stranger; uninstall refuses directories that do not really resolve inside the bridge's storage folder (a planted junction gets a refusal, not a recursive delete); and the certification rail accepts only exact versions, printing no copy-paste command for a registry string it cannot trust. The README gained a Security model section with the rest, including the honest one: the agent can run commands in your terminal, on purpose.
- **The pill whale got redrawn by its owner.** The resting whale's belly is now a single open arc whose pocket reads at status-bar size without a hairline fighting the pixel grid, and the message chip's outline slimmed to 28 units. The stopped state still drops the whole chip and keeps the belly.

## 0.1.2

- **The pill whale slims down.** Outline strokes cut from 70 to 40 viewBox units (~0.6 px at status-bar size): the same artwork, no longer chunky. The stopped state now drops the whole message chip — ring and chevron alike — while the slim belly line stays on the resting whale.

## 0.1.1

- **The pill whale learned to speak monochrome.** The pill font now traces its own artwork, tuned for one ink: the terminal bubble is a chunky ring that floats above the whale only while the harness runs, and the belly reads as an outlined crescent instead of merging into a blob. Hairlines cannot survive the pill (anything under ~70 viewBox units is sub-pixel at status-bar size), so every line was measured, not eyeballed.
- **The Marketplace icon fills its tile now.** The builder had been drawing the whale into the top-left quarter of the canvas — a viewBox-units-as-pixels coincidence at the old canvas size — and shipping it; the ink bbox is now fitted to the tile.

## 0.1.0

First build. (Honest history: 0.1.0 itself never reached the Marketplace — the first listing went up with 0.1.3, uploaded through the publisher portal.) Alpha testers come through extension search, and every later fix arrives as an automatic update. Harness traffic reaching your usage totals needs vLLM-Copilot 1.37.1 or newer.

- **First-run setup, and an honest look at the machine before it.** A fresh install now says what it needs instead of waiting for a command nobody knows. The setup offer names the one-time harness download, and every start checks for a real Node.js 22 or newer on PATH and a working npm before anything downloads. A missing prerequisite is named with its version and the fix, not with npm's own error text.
- **The status-bar pill wears the whale.** Running shows the whale with its spout going; stopped shows the same whale, spray gone. The pill glyphs and the Marketplace icon are now both built from one vector artwork (`npm run icons:build`), so gallery and pill can never show two different whales.
- **The harness is now an editor tab, not a browser page.** It opens chromeless inside VS Code (default `panel`): no address bar, and each tab is named after the conversation it shows (`DSH — <chat>`). The view's address survives harness restarts, and tabs come back on their own after window reloads.
- **Several harness views.** The `+` in the tab's title bar (or "DSH: Open Another Harness View") opens a second full GUI with its own session selection; views split, and "Move into New Window" gives a chat a window of its own.
- **VS Code shortcuts answer from inside the harness**: `F1`/`Ctrl+Shift+P`, `Ctrl+P`, `Ctrl+B`, `Ctrl+,`, `Ctrl+W` and friends work wherever the cursor is — and every shortcut the harness handles itself stays the harness's.
- New settings: `dsh-bridge.openIn` (default `panel`; also `appWindow`, `embedded`, `external`), `dsh-bridge.embedPort` (stable panel address), `dsh-bridge.keyboardBridge`, and `dsh-bridge.logLevel` (`debug` mirrors harness chatter for diagnostics).
- **Editor shortcuts from inside the harness now travel two roads.** `Ctrl+Shift+P` and friends could lean on a single messaging hop out of the webview, the same hop that taught the tab title to report twice; chords now arrive over both, and each press executes exactly once and shows up in the bridge log at the default level.
- **Phantom "harness requests running" counts are gone.** A harness killed mid-turn left its active-request records behind, so the pill counted work that no longer existed and a restart's drain waited on dead processes. A fresh start now clears the dead harness's records (observed: two ghosts, one of them six hours old).
- **Plugin toggles now come with an honest verdict and a restart button.** Toggling a plugin inside the harness writes the profile but cannot hot-apply: this dsh build deadlocks its own live reload once a profile carries any patch content, so its "Could not enable" toast overshoots and the change waits for a restart (an upstream bug, documented with a minimal repro). The bridge now notices the toggle in the profile files and says exactly that: "Plugin changes are saved but cannot hot-apply; restart now", draining in-flight turns first. The bridge's own generated config moved from a boot-only overlay file into the profile's patch layer, where you can see it and edit around it, and the fragile `--patch` boot flag is gone.

## 0.0.17

- **Harness tabs no longer come back from the dead.** The embedded harness view now closes when the harness stops, restarts, or the window shuts down, instead of lingering until the next boot, where the dead address would hide the window's menus. The status-bar pill reopens it in one click.

## 0.0.16

- **Menus work again after restarts.** A harness tab left open across a restart can never reconnect (the harness gets a fresh address every launch), and VS Code's built-in browser hides the window's menus while showing that error page. The bridge now closes those stale tabs itself at startup; the command "Close Stale Harness Browser Tabs" does it by hand if ever needed.

## 0.0.15

First public version. The bridge runs the [DeepSeek Harness](https://www.npmjs.com/package/@deepseek-ai/dsh) (dsh) entirely on your vLLM-Copilot registry: same models, servers, sampling configs, and personalities, no DeepSeek account and no vendor login. dsh itself stays 100% upstream.

- One supervised harness. The extension installs the pinned dsh runtime into its own directory, launches the web UI, and shares one instance across all editor windows: restored windows join the running harness instead of fighting over it.
- Your registry, honestly. The harness model list is your vLLM-Copilot registry with models your servers stopped serving hidden, and models are shown by their display names, never by ids containing server hostnames.
- The harness opens inside VS Code by default, in the built-in Browser area, or in the system browser by setting.
- Editor tools for the agent, over MCP: read open files and selections, read the problem panel, open files and diffs for your review, run commands visibly in your editor terminal, send you notifications, and ask you questions when a decision belongs to the human.
- Your token totals include harness traffic. Completed requests are folded into the vLLM-Copilot usage ledger exactly once, resets included.
- Config changes never cut a live turn. Registry edits and restarts wait for in-flight harness requests to finish, then say so if anything was cut.
- Privacy: dsh's telemetry, account, and DeepSeek-service rows are disabled in the generated config; the harness never phones DeepSeek.
