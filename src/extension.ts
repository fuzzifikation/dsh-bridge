/**
 * Editor glue. Everything with an `import * as vscode` lives here, in
 * `settings.ts`, or in `editor-tools.ts` (the MCP tool implementations),
 * which is what keeps the bridge's logic testable in plain node.
 */
import * as vscode from 'vscode'
import { randomUUID } from 'node:crypto'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import * as path from 'node:path'
import { Bridge } from './bridge/bridge.js'
import { bridgePaths, ensureBridgeDirs } from './bridge/paths.js'
import { asLedgerPort, type LedgerPort } from './bridge/api.js'
import { ControlServer } from './bridge/control-server.js'
import { createCoreCatalogSource } from './bridge/core-catalog.js'
import { createEditorTools } from './bridge/editor-tools.js'
import { readBridgeSettings, readMainRegistry, mainExtensionInstalled, MAIN_EXT_ID } from './bridge/settings.js'
import { drainActiveRequests } from './bridge/ingest.js'
import { originAnswers, readServedHostPorts, servedUrlsFile } from './bridge/served-urls.js'

const RESTART_DEBOUNCE_MS = 1500
/** Deactivate must not hold the extension host hostage, unlike a deliberate restart. */
const SHUTDOWN_DRAIN_BUDGET_MS = 5000
/**
 * Bridge settings the harness reads at boot, so changing one means a restart.
 * Everything else (`drainTimeoutSeconds` is read per stop, `ingestIntervalSeconds`
 * just re-arms a timer, `autoStart` gates starting) must never cut a live turn.
 */
const BRIDGE_RESTART_KEYS = ['defaultModelId', 'titleModel', 'titleMaxTokens', 'compactionModel', 'compactionMaxTokens', 'dshVersion'] as const

let output: vscode.LogOutputChannel | undefined

function log(): { info(m: string): void; warn(m: string): void; error(m: string): void } {
  output ??= vscode.window.createOutputChannel('DeepSeek Harness Bridge', { log: true })
  return output
}

/**
 * The ledger port, re-resolved per pass: the main extension may activate after
 * us, or be updated/reloaded, and a port captured once at activation would keep
 * pointing at a stale or absent export forever.
 */
function resolveLedgerPort(): LedgerPort | undefined {
  const ext = vscode.extensions.getExtension(MAIN_EXT_ID)
  if (!ext) return undefined
  try {
    return asLedgerPort(ext.isActive ? ext.exports : undefined)
  } catch (err) {
    log().warn(`could not read the vLLM-Copilot API: ${(err as Error).message}`)
    return undefined
  }
}

/**
 * Show the harness UI per `dsh-bridge.openIn`. `embedded` (default) uses the
 * editor's own browser view: VS Code 1.140 removed the Simple Browser
 * extension (its `simpleBrowser.show` is gone from the command registry,
 * certified on the extension-host rail) and shipped a built-in Browser area,
 * so the probe tries the new door first and keeps the old one for older
 * builds and VSCodium. `external`, or either embedded door missing, ends in
 * the system browser, said out loud. A chromeless webview panel was built
 * and retired the same day (0.0.10/0.0.11): the harness authenticates its
 * browser session with a `SameSite=Strict` HttpOnly cookie, and Chromium
 * never sends Strict cookies from a cross-site frame, so the iframe only
 * ever reached the server's 401 text. The Browser area shows the page
 * top-level, where the cookie works. Do not re-propose the iframe.
 * The token-bearing URL only ever crosses as a command argument.
 */
async function openHarnessUrl(url: string): Promise<void> {
  const mode = vscode.workspace.getConfiguration('dsh-bridge').get<string>('openIn', 'embedded')
  if (mode === 'embedded') {
    const commands = await vscode.commands.getCommands(true)
    const door = commands.includes('workbench.action.browser.open')
      ? 'workbench.action.browser.open'
      : commands.includes('simpleBrowser.show')
        ? 'simpleBrowser.show'
        : undefined
    if (door) {
      try {
        await vscode.commands.executeCommand(door, url)
        return
      } catch {
        void vscode.window.showInformationMessage(
          'The embedded browser view refused to open, so the harness opens in the system browser instead.',
        )
      }
    } else {
      void vscode.window.showInformationMessage(
        'This editor build provides no embedded browser view, so the harness opens in the system browser instead.',
      )
    }
  }
  await vscode.env.openExternal(vscode.Uri.parse(url))
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  const logger = log()
  const version = String(context.extension.packageJSON.version ?? '0.0.0')
  const paths = bridgePaths(context.globalStorageUri.fsPath)
  ensureBridgeDirs(paths)

  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 90)
  status.command = 'dshBridge.open'
  context.subscriptions.push(status)

  // The editor control channel: the harness's MCP client dials this loopback
  // server to reach the editor tools. Token per activation, handed to the
  // harness ONLY through the generated overlay row; never logged.
  const editorTools = createEditorTools({ disposables: context.subscriptions })
  const controlToken = randomUUID()
  let control: ControlServer | undefined
  let controlStart: Promise<string> | undefined
  function ensureControl(): Promise<string> {
    control ??= new ControlServer({
      token: controlToken,
      activeDir: paths.active,
      mcp: { tools: () => editorTools.tools(), serverInfo: { name: 'vllmc-editor', version } },
      log: logger,
    })
    controlStart ??= control.listen().catch((err: Error) => {
      controlStart = undefined
      throw err
    })
    return controlStart
  }

  /**
   * The staged core's catalog surface, through the same loader the node rails
   * build, so `bridge:check` exercises the code this window actually runs.
   * The PROFILE's installed copy, not vendor/: pnpm resolved the core's bare
   * dependencies beside it, while the vendor staging has no node_modules and
   * would fail on the core's own imports.
   */
  const catalogSource = createCoreCatalogSource({
    entryFile: () => path.join(paths.profileModules, 'vllm-copilot-core', 'core', 'index.js'),
    log: logger,
  })

  const bridge = new Bridge({
    extensionRoot: context.extensionPath,
    extensionVersion: version,
    paths,
    log: logger,
    dshVersion: () => readBridgeSettings().dshVersion || readBundledPin(),
    registry: () => {
      const registry = readMainRegistry()
      // A configured personality only reaches the harness through the
      // snapshot's `personalityFile`, so resolve each model's file here.
      // Relative or missing paths are skipped: a guess at a personality path
      // is how the wrong persona gets attached to a model.
      const personalityFiles: Record<string, string> = {}
      for (const model of registry.models) {
        const file = model.systemMessageReplacementsFile
        if (typeof file === 'string' && file.trim() && path.isAbsolute(file) && existsSync(file)) {
          personalityFiles[model.id] = file
        }
      }
      return {
        ...registry,
        personalityFiles,
        fixEmptyToolParameters: vscode.workspace.getConfiguration('vllm-copilot').get<boolean>('fixEmptyToolParameters'),
      }
    },
    choices: () => {
      const s = readBridgeSettings()
      return {
        defaultModelId: s.defaultModelId || undefined,
        title: s.title,
        compaction: s.compaction,
        drainTimeoutMs: s.drainTimeoutSeconds * 1000,
      }
    },
    ledgerPort: resolveLedgerPort,
    mainExtension: () => {
      const ext = vscode.extensions.getExtension(MAIN_EXT_ID)
      return ext ? { path: ext.extensionPath, version: String(ext.packageJSON.version ?? 'unknown') } : undefined
    },
    editorWorkspaceFolder: () => {
      const [first, second] = vscode.workspace.workspaceFolders ?? []
      if (!first) return undefined
      if (second) {
        logger.warn(`the window has multiple root folders; the harness workspace is the first one ("${first.name}")`)
      }
      return first.uri.fsPath
    },
    controlEndpoint: () => {
      const url = control?.url
      return url ? { url, token: controlToken } : undefined
    },
    coreCatalog: catalogSource,
    onUnexpectedExit: (info) => {
      render()
      // The URL died with the server; a tab nobody can serve is tomorrow's
      // poisoned boot, so bury it now. The pill reopens the harness in a click.
      sweepNow()
      void vscode.window
        .showWarningMessage(
          `The DeepSeek Harness exited on its own (code ${info.code}, signal ${info.signal}). The bridge log has the last output.`,
          'Show Log',
          'Restart Harness',
        )
        .then((choice) => {
          if (choice === 'Show Log') void output?.show()
          if (choice === 'Restart Harness') void guardedStart()
        })
    },
  })

  function readBundledPin(): string {
    // The certified version lives in exactly one file, the same one the node
    // rails read. The setting overrides it; nothing else duplicates it. An
    // unreadable pin aborts the start: quietly booting whatever npm calls
    // "latest" would run an uncertified dsh against overlays certified
    // against a different composition, the exact drift the pin exists to stop.
    try {
      const raw = readFileSync(path.join(context.extensionPath, 'config', 'dsh.json'), 'utf8')
      const pinned = String((JSON.parse(raw) as { pinned?: string }).pinned ?? '')
      if (!/^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/.test(pinned)) {
        throw new Error(`config/dsh.json carries no exact pinned version (got ${JSON.stringify(pinned)})`)
      }
      return pinned
    } catch (err) {
      const message = (err as Error).message
      logger.error(`the bundled dsh pin is unreadable: ${message}`)
      throw new Error(`cannot start the harness: the certified dsh pin in config/dsh.json is unreadable (${message}); refusing to fall back to an uncertified "latest"`)
    }
  }

  // Declared before render(): the pill reads this promise to show the
  // starting state, and render() runs at activation, before any start.
  let starting: Promise<string | undefined> | undefined

  function render(): void {
    const active = bridge.activeRequests()
    // The palette reflects reality. Start hides itself while the harness runs,
    // and nothing offers "Open" before there is a URL to open.
    void vscode.commands.executeCommand('setContext', 'dshBridge.running', bridge.supervisor.running)
    void vscode.commands.executeCommand('setContext', 'dshBridge.ownerAvailable', mainExtensionInstalled())
    if (bridge.supervisor.running) {
      status.text = `$(radio-tower) DSH${active ? ` $(zap)${active}` : ''}`
      status.tooltip = new vscode.MarkdownString(
        [
          `**DeepSeek Harness: running**`,
          '',
          `URL: \`${bridge.supervisor.url ? bridge.supervisor.url.replace(/\?.*$/, '?<token redacted>') : 'unknown'}\``,
          `In-flight requests: ${active}`,
          bridge.preparedInfo ? `dsh ${bridge.preparedInfo.dshVersion}, core ${bridge.preparedInfo.coreVersion}` : '',
          bridge.preparedInfo ? `privacy rows disabled: ${bridge.preparedInfo.rowsDisabled}` : '',
          '',
          'Click to open the harness.',
        ]
          .filter(Boolean)
          .join('\n'),
      )
      status.backgroundColor = undefined
      // Re-arm the click on every transition INTO running. The command was
      // set to "start" while stopped (below), and a stale one made the
      // running pill execute a no-op Start: the tooltip said "click to
      // open" and the click opened nothing, silently, because starting an
      // already-running harness returns its URL. Every field render claims
      // must be written by every branch that displays it.
      status.command = 'dshBridge.open'
      return
    }
    if (starting) {
      // A cold first run installs the dsh runtime and the profile with pnpm
      // before anything can listen; two-plus minutes of "stopped" reads as
      // death. Say what is happening instead of gaslighting the user.
      status.text = '$(sync~spin) DSH: starting'
      status.tooltip = new vscode.MarkdownString([
        '**DeepSeek Harness: starting**',
        '',
        'The first run after an install downloads and installs the harness once.',
        'That takes a few minutes; later starts take seconds.',
        'Progress: "DeepSeek Bridge" output channel.',
      ].join('\n'))
      status.command = 'dshBridge.start'
      status.backgroundColor = undefined
      return
    }
    if (!mainExtensionInstalled()) {
      status.text = '$(debug-disconnect) DSH: no vLLM-Copilot'
      status.tooltip = 'Install the vLLM-Copilot extension to point the DeepSeek Harness at your own models. Until then the bridge does nothing.'
      status.command = 'workbench.view.extensions'
      return
    }
    status.text = '$(debug-disconnect) DSH: stopped'
    status.tooltip = 'The DeepSeek Harness is not running. Click to start it.'
    status.command = 'dshBridge.start'
  }
  render()
  status.show()

  /**
   * Stale embedded tabs kill the window's menus, and the harness manufactures
   * them by design: port and token are reissued every boot, so a harness tab
   * restored after a restart can never connect. In VS Code 1.140 the browser
   * tab is a native Electron child view, and a restored fail-load one breaks
   * the window's menu layer (owner-reproduced 2026-10-11: tab open across a
   * restart equals dead menus; closing the tab afterwards does NOT heal the
   * menus, only a window reload does; upstream sibling
   * microsoft/vscode#317715). The bridge cannot prevent the restore and
   * cannot heal the latched damage, so this sweep is prevention for future
   * boots, executed the moment the bridge wakes: it closes exactly its own
   * zombies, and a closed tab is never restored. Nothing else is ever
   * touched: tabs match on loopback host:ports we ourselves served, and
   * never while the origin answers anything.
   */
  async function sweepStaleTabs(): Promise<number> {
    const hostPorts = readServedHostPorts(servedUrlsFile(paths.vllmc))
    let closed = 0
    for (const hostPort of hostPorts) {
      for (;;) {
        if (!tabGroupShowing(hostPort)) break
        if (await originAnswers(hostPort)) {
          logger.info(`keeping the browser tab on ${hostPort}: something answers there now`)
          break
        }
        if (!(await closeStaleTab(hostPort))) {
          logger.warn(`could not close the stale harness tab on ${hostPort}: close it by hand, then reload the window to bring its menus back`)
          break
        }
        closed += 1
        logger.info(`closed the stale harness tab on ${hostPort}: its URL died with the last session`)
      }
    }
    if (closed)
      logger.info(
        `stale-tab sweep: closed ${closed} dead harness tab(s); the next session starts clean, and if this window's menus are hidden, one "Developer: Reload Window" brings them back`,
      )
    return closed
  }

  /** Browser tabs carry the origin as label, so `127.0.0.1:port` IS the match. */
  function tabGroupShowing(label: string): vscode.TabGroup | undefined {
    for (const group of vscode.window.tabGroups.all) {
      if (group.tabs.some((tab) => tab.label === label)) return group
    }
    return undefined
  }

  /**
   * 1.140 ships no command that closes one NAMED tab (`workbench.action.closeTabs`
   * is absent from the build, verified against every bundle chunk), so the
   * close walks to the tab: cycle groups until the target's group is active,
   * cycle tabs inside it until the target is active, close the active editor.
   * Focus is a suggestion, not a promise, so reality is re-read after every
   * step and the walk is bounded. This dance is Microsoft's fault, not ours.
   */
  async function closeStaleTab(label: string): Promise<boolean> {
    const nap = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))
    for (let step = 0; step < 24; step += 1) {
      const group = tabGroupShowing(label)
      if (!group) return true
      const active = vscode.window.tabGroups.activeTabGroup
      if (active.viewColumn === group.viewColumn && active.activeTab?.label === label) {
        await vscode.commands.executeCommand('workbench.action.closeActiveEditor')
        await nap(400)
      } else {
        await vscode.commands.executeCommand(
          active.viewColumn === group.viewColumn ? 'workbench.action.nextEditorInGroup' : 'workbench.action.focusNextGroup',
        )
        await nap(60)
      }
    }
    return !tabGroupShowing(label)
  }

  /** Fire the sweep without ever blocking or rejecting a caller. */
  function sweepNow(): void {
    void sweepStaleTabs().catch((err: Error) => logger.warn(`stale-tab sweep failed: ${err.message}`))
  }

  // The sweep runs before anything else spends time: every second a fail-load
  // view sits in the window is a second the user cannot open a menu.
  sweepNow()

  /**
   * Shutdown variant: close this window's harness tabs whether or not the
   * origin still answers, because no server will own that URL in the NEXT
   * session, and only a tab that was never restored cannot poison a boot.
   * Best effort: the host may not wait for the focus walk, and whatever
   * survives is exactly what the next activation's sweep was built for.
   */
  async function closeOwnEmbeddedTabs(): Promise<void> {
    for (const hostPort of readServedHostPorts(servedUrlsFile(paths.vllmc))) {
      for (;;) {
        if (!tabGroupShowing(hostPort)) break
        if (!(await closeStaleTab(hostPort))) break
        logger.info(`closed the harness tab on ${hostPort} before shutdown: dead URLs must not survive into the next session`)
      }
    }
  }

  async function guardedStart(): Promise<string | undefined> {
    if (bridge.supervisor.running && bridge.supervisor.url) return bridge.supervisor.url
    // Best effort: a harness whose control channel failed to start still
    // runs; its agent simply never sees the editor tools (the MCP client
    // cannot dial a dead endpoint and mounts nothing).
    await ensureControl().catch((err: Error) => logger.warn(`editor control channel did not start: ${err.message}`))
    starting ??= bridge
      .start()
      .catch((err: Error) => {
        logger.error(`harness failed to start: ${err.message}`)
        void vscode.window.showErrorMessage(`DeepSeek Harness failed to start: ${err.message}`, 'Show Log').then((choice) => {
          if (choice === 'Show Log') void output?.show()
        })
        return undefined
      })
      .finally(() => {
        starting = undefined
        render()
      })
    // The pill only learns about the flight if we paint it now; the finally
    // above repaints when it lands.
    render()
    return starting
  }

  /**
   * Registry edits must reach the harness, and the harness reads its config at
   * boot, so an edit means a restart. The restart drains first: a user who
   * tweaks a model while a turn is in flight must not watch that turn die.
   *
   * Auto-restart is the spawning window's job alone. Every window hears the
   * same configuration event, and a borrowing window that restarted would
   * tree-kill the harness it does not own, while the concurrent stop and
   * DSH_HOME sweep of two windows can cut down a freshly respawned harness
   * mid-boot. The owner window hears the same event and performs the swap.
   */
  let pendingRestart: NodeJS.Timeout | undefined
  function scheduleRestart(reason: string): void {
    if (!bridge.supervisor.running) {
      // A boot in flight reads its settings at prepare time; a change landing
      // mid-start would otherwise be swallowed until the NEXT edit, leaving a
      // harness built from stale config proudly running. Re-check after the
      // debounce until the boot settles; a failed start ends the loop.
      if (starting) setTimeout(() => scheduleRestart(reason), RESTART_DEBOUNCE_MS).unref?.()
      return
    }
    if (pendingRestart) clearTimeout(pendingRestart)
    pendingRestart = setTimeout(() => {
      void (async () => {
        if (bridge.supervisor.adopted) {
          logger.info(`not restarting (${reason}): this window borrows the harness; the window that spawned it applies the change`)
          return
        }
        logger.info(`restarting the harness: ${reason}`)
        const settings = readBridgeSettings()
        const preview = await drainActiveRequests(paths.active, 0)
        if (preview.remaining > 0 && settings.drainTimeoutSeconds > 0) {
          void vscode.window.showInformationMessage(
            `Waiting for ${preview.remaining} harness request(s) to finish before applying this change.`,
          )
        }
        await bridge.restart().then((result) => {
          if (!result.drained) {
            void vscode.window.showWarningMessage(`${result.remaining} in-flight harness request(s) were cut while applying this change.`)
          }
        })
        render()
        // A restart reissues port and token, so the open tab just became a
        // corpse with a live-looking page. Sweep before the window can quit
        // with it and restore a dead URL into the next session.
        sweepNow()
      })()
    }, RESTART_DEBOUNCE_MS)
  }

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (
        event.affectsConfiguration('vllm-copilot.servers') ||
        event.affectsConfiguration('vllm-copilot.models') ||
        event.affectsConfiguration('vllm-copilot.fixEmptyToolParameters')
      ) {
        // No early return: one configuration event can carry a registry edit
        // AND a bridge edit (bulk settings change), and the bridge half below
        // re-arms the ingest timer. Skipping it would silently keep the old
        // cadence until the next restart.
        scheduleRestart('the vLLM-Copilot registry changed')
      }
      if (!event.affectsConfiguration('dsh-bridge')) return
      // Only boot-time settings justify draining and restarting a live
      // session. The ingest cadence re-arms here so the setting takes effect
      // without a restart, and switching autoStart on may start a stopped
      // harness; none of these may cut an in-flight turn.
      if (event.affectsConfiguration('dsh-bridge.ingestIntervalSeconds')) armIngestTimer()
      if (event.affectsConfiguration('dsh-bridge.autoStart') && readBridgeSettings().autoStart && !bridge.supervisor.running && !starting) {
        void guardedStart()
      }
      if (BRIDGE_RESTART_KEYS.some((key) => event.affectsConfiguration(`dsh-bridge.${key}`))) {
        scheduleRestart('a bridge setting changed')
      }
    }),
  )

  // Ingestion runs on a timer rather than on a file watch: the outbox is a
  // directory the harness writes into from another process, and polling a
  // directory is portable in a way that reliable inotify events are not.
  let ingestTimer: NodeJS.Timeout | undefined
  let ingesting = false
  async function ingestPass(): Promise<void> {
    if (ingesting) return
    ingesting = true
    try {
      const outcome = await bridge.ingest()
      if (outcome.accepted || outcome.duplicate || outcome.malformed) {
        logger.info(
          `usage ingest: ${outcome.accepted} new, ${outcome.duplicate} duplicate, ${outcome.preReset} before last reset` +
            `${outcome.malformed ? `, ${outcome.malformed} quarantined` : ''}` +
            `${outcome.rejected ? `, ${outcome.rejected} refused` : ''}` +
            `${outcome.deferred ? `, ${outcome.deferred} deferred` : ''}`,
        )
      } else if (outcome.deferred && !ingestTimerWarned) {
        ingestTimerWarned = true
        logger.warn(
          `${outcome.deferred} harness request(s) are waiting for a vLLM-Copilot version that accepts them. ` +
            'Update vLLM-Copilot to see this traffic in your dashboard totals.',
        )
        void vscode.window
          .showWarningMessage(
            'Harness traffic is not reaching your dashboard totals: this vLLM-Copilot version does not accept external usage yet. Update it to fix this.',
            'Show Log',
          )
          .then((choice) => {
            if (choice === 'Show Log') void output?.show()
          })
      }
    } catch (err) {
      logger.warn(`usage ingest pass failed: ${(err as Error).message}`)
    } finally {
      ingesting = false
      render()
    }
  }
  let ingestTimerWarned = false

  function armIngestTimer(): void {
    const seconds = Math.max(2, readBridgeSettings().ingestIntervalSeconds)
    if (ingestTimer) clearInterval(ingestTimer)
    ingestTimer = setInterval(() => void ingestPass(), seconds * 1000)
    ingestTimer.unref?.()
  }
  armIngestTimer()
  void ingestPass()

  // Registered before any early return below: activation can bail out early
  // (no vLLM-Copilot, empty registry) and a timer armed before that would
  // otherwise outlive the extension with nothing left to clear it.
  context.subscriptions.push({
    dispose: () => {
      if (ingestTimer) clearInterval(ingestTimer)
      if (pendingRestart) clearTimeout(pendingRestart)
      control?.close()
    },
  })

  /** What the status bar cannot hold: versions, handoff health, queue depth.
   *  Never a URL with its token and never a server id built from a hostname. */
  async function showReport(): Promise<void> {
    const info = bridge.preparedInfo
    const lines = [
      `Harness: ${bridge.supervisor.running ? 'running' : 'stopped'}`,
      `dsh version: ${info?.dshVersion ?? 'not prepared'}`,
      `vLLM-Copilot core: ${info?.coreVersion ?? 'not staged'}`,
      `snapshot version: ${info?.snapshotVersion ?? 'not written'}`,
      `privacy rows disabled: ${info?.rowsDisabled ?? 'unknown'}`,
      `in-flight requests: ${bridge.activeRequests()}`,
      `pending usage records: ${readdirSync(paths.outbox).filter((n) => n.endsWith('.json')).length}`,
      `editor control channel: ${control?.url ? `listening on ${control.url}` : 'not started'}`,
      `ledger handoff: ${resolveLedgerPort() ? 'available' : 'not offered by this vLLM-Copilot version'}`,
      '',
      'Harness URL tokens and server ids are never shown here.',
    ]
    const choice = await vscode.window.showInformationMessage(lines.join('  \n'), 'Show Log')
    if (choice === 'Show Log') output?.show()
  }

  context.subscriptions.push(
    vscode.commands.registerCommand('dshBridge.start', async () => {
      await guardedStart()
      render()
    }),
    vscode.commands.registerCommand('dshBridge.stop', async () => {
      const result = await bridge.stop()
      if (!result.drained) {
        void vscode.window.showWarningMessage(`${result.remaining} in-flight harness request(s) were cut by this stop.`)
      }
      render()
      // The tab's server is gone by the user's own hand: close the tab too.
      sweepNow()
    }),
    vscode.commands.registerCommand('dshBridge.restart', async () => {
      const result = await bridge.restart()
      if (!result.drained) {
        void vscode.window.showWarningMessage(`${result.remaining} in-flight harness request(s) were cut by this restart.`)
      }
      render()
      sweepNow()
    }),
    vscode.commands.registerCommand('dshBridge.open', async () => {
      const url = bridge.supervisor.url ?? (await guardedStart())
      if (!url) return
      // The URL carries the UI's auth token, so it is opened programmatically
      // and never printed to a log or a notification a user might paste.
      await openHarnessUrl(url)
    }),
    vscode.commands.registerCommand('dshBridge.showLogs', async () => {
      output?.show()
    }),
    vscode.commands.registerCommand('dshBridge.report', () => showReport()),
    // Visible on purpose: if a stale harness tab ever eats the menus again
    // (ours or a restored one the sweep missed), this is the recovery button
    // a keyboard user can reach without a mouse menu, and the rail's handle
    // on the exact production path.
    vscode.commands.registerCommand('dshBridge.sweepStaleTabs', async () => {
      await sweepStaleTabs()
    }),
  )

  // The main extension is expected but not required: with it absent the harness
  // would have no models to offer, so the bridge stays dark and says why once,
  // instead of failing on every start or nagging on every window.
  if (!mainExtensionInstalled()) {
    logger.warn('vLLM-Copilot is not installed; the bridge stays idle and the harness is not launched')
    void vscode.window
      .showWarningMessage(
        'The DeepSeek Harness Bridge needs the vLLM-Copilot extension. Without it, dsh has no models to offer and the bridge does nothing.',
        'Install vLLM-Copilot',
        'Show Log',
      )
      .then(async (choice) => {
        if (choice === 'Install vLLM-Copilot') await vscode.commands.executeCommand('extension.open', MAIN_EXT_ID)
        if (choice === 'Show Log') output?.show()
      })
    return
  }

  // Activate the main extension so its exports (the ledger handoff) are there
  // before the first ingest pass instead of after it.
  try {
    await vscode.extensions.getExtension(MAIN_EXT_ID)?.activate()
  } catch (err) {
    logger.warn(`activating vLLM-Copilot failed: ${(err as Error).message}`)
  }

  const registry = readMainRegistry()
  if (registry.models.length === 0) {
    logger.warn('the vLLM-Copilot registry has no models; the harness is not launched')
    void vscode.window
      .showInformationMessage('Add a server and a model in vLLM-Copilot settings, then start the DeepSeek Harness.', 'Open vLLM-Copilot Settings', 'Start Harness')
      .then((choice) => {
        if (choice === 'Open vLLM-Copilot Settings') void vscode.commands.executeCommand('workbench.action.openSettings', '@ext:system-sciences.vllm-copilot vllm-copilot')
        if (choice === 'Start Harness') void guardedStart()
      })
    return
  }

  if (readBridgeSettings().autoStart) await guardedStart()
  render()

  context.subscriptions.push({
    // Deactivate is best effort: it does not run at all when the host dies,
    // which is what the start-time reap of detached survivors is for.
    dispose: () => {
      // Tabs die with the session, unconditionally and first: a restored
      // fail-load browser view poisons the window's menus before any
      // extension can react (docs/upstream-issues.md section 3), and menu
      // damage latches until a reload, so prevention is the only cure.
      void closeOwnEmbeddedTabs().catch(() => {})
      // A borrowed harness belongs to a window that is still open: closing
      // this one must leave it, its pid record, and its detached servers
      // running. Only the window that spawned the harness may end it.
      if (bridge.supervisor.adopted) bridge.supervisor.release()
      else void bridge.supervisor.stop({ drainMs: SHUTDOWN_DRAIN_BUDGET_MS })
    },
  })
}

export function deactivate(): void {
  /* the dispose handlers above do the shutdown work */
}
