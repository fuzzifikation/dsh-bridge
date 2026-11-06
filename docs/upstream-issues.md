# Upstream issues to file

Reports we owe the DeepSeek Harness team, drafted from certified behavior in our pinned composition (`@deepseek-ai/dsh` per `config/dsh.json`). No private hosts or paths appear below.

Filed 2026-10-06 as Discussions (the repository's issue tracker is disabled): [notice acknowledgement](https://github.com/deepseek-ai/deepseek-harness/discussions/9001), [webview cookies](https://github.com/deepseek-ai/deepseek-harness/discussions/9002).

## 1. Preview Notice acknowledgement never persists without a DeepSeek account

The first-run "Preview Notice" modal gates on `ui-settings-general.welcomeNoticeVersion` equaling the client constant (exact equality, `@deepseek-ai/dsh-client-ui-settings-models`). Clicking Continue in a profile with no DeepSeek account logs "The acknowledgement could not be saved" and sends no RPC at all; the modal reappears every boot forever. The setting itself is writable by other means (a patch-layer config row with the field set makes the notice never render), so the storage layer is fine and only the acknowledgement path is broken in the no-account composition.

Request: persist the acknowledgement through the same local settings path when no account is connected.

Current bridge workaround: the generated overlay states `welcomeNoticeVersion` itself, pinned to the upstream constant and bumped with each dsh pin update.

## 2. Harness UI cannot be embedded in editor webviews (cookie policy)

The web server's browser session cookie is `HttpOnly; SameSite=Strict` (dsh-client-connection, `sessionCookie()`), and the `/api` transport authenticates with that cookie only. Chromium never stores or sends Strict cookies in a cross-site frame, so embedding the harness in any editor webview (VS Code extension panels, every other IDE's equivalent) shows only the 401 text. Top-level browser tabs and desktop webview shells are unaffected, which is why nobody notices upstream.

Request: support `Partitioned` (CHIPS) cookies, which are exactly designed for authenticated loopback frames on trustworthy origins like `http://127.0.0.1`, or accept the session token through a header fallback for embedded clients. Either one makes "open the harness inside the editor without its own browser chrome" possible for every editor integration, not just ours.

Current bridge posture: we open the harness in VS Code's built-in Browser area (top-level, cookie works, toolbar visible). A bridge-side proxy rewriting cookie attributes was evaluated and rejected.

---

# VS Code (microsoft/vscode), DRAFT, not filed: pending owner go

Filed against a different upstream than the two above. Filed here locally first; file on microsoft/vscode only after the owner's live go, with a fresh `Help: Report Issue` system-info dump attached.

## 3. A restored fail-load Browser tab hides every menu in the window (menus open behind the window)

Version observed: VS Code 1.140 (user build), Windows. No extension required to reproduce:

1. Open the built-in Browser and navigate to a dead loopback URL, e.g. `http://127.0.0.1:59999/x`. The tab shows the connection error page.
2. `Developer: Reload Window`. The tab restores and shows the error page again.
3. Open any menu: File, right-click context menus, quick picks. The menu opens and is not visible: it renders under the browser view, and users describe it as "menus open behind the window".
4. Close the browser tab. Menus are STILL broken. They only work again after `Developer: Reload Window`. A browser tab whose page loads successfully does NOT cause the bug at any step; it is specifically the restored fail-load view, and the damage latches: destroying the view afterwards never repairs the menus.

Measured timeline from our product's logs (extension present, but the repro above needs none): workbench restore fails the view's initial load at T+2.3 s (`main.log`: `[BrowserViewMainService] Failed to load initial URL ... ERR_CONNECTION_REFUSED`); the extension closes the tab at T+4.1 s; menus remain unreachable until window reload minutes later.

Evidence from our product (every byte here reproducible without it): a z-order recorder (`EnumWindows`, 120 ms sampling) shows no new OS window from any Code process while menus are "open": workbench menus are DOM, and the Browser tab is a native Electron child view (`contentView.addChildView` + `setBounds` in `out/mainImpl.js`, `BrowserViewMainService`), which composites above the window's web content. What latches after the fail-load restore is evidently not just the visible surface: closing the tab disposes it, yet menus keep opening beneath an invisible something until the window reloads. Sibling report microsoft/vscode#317715 (May 2026, "VSCode menu is behind editing window", closed `info-needed` because the reporter found no pattern; the pattern is a restored browser view in fail-load state).

Request: repair the menu layer when such a view is destroyed or hidden, and ideally never let a child view outrank popup-weight DOM in the first place (hide or lower the native browser view while a workbench menu, quick pick, or context menu is up, the same dance every desktop app does with child windows).

Current bridge posture: the DeepSeek Harness Bridge opens local harness UIs in this browser view, whose URL is dead by design after every restart, so it hits this bug on every restored session. Since 0.0.16 it closes its own stale tabs at activation, which keeps later sessions clean because a closed tab is never restored; it cannot heal the one session that arrives poisoned, because no in-window action short of `Developer: Reload Window` repairs the menus. Users of any extension (or any manual localhost tab) are still exposed with no workaround at all.
