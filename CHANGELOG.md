# Changelog

## Unreleased

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
