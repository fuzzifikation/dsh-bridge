/**
 * Tripwire for the poisoned-window bug (owner-reproduced 2026-10-11): a
 * harness browser tab restored after a restart can never connect (the port
 * and token are reissued every boot), and in VS Code 1.140 that fail-load
 * native browser view paints over the workbench DOM and hides every menu in
 * the window. The sweep must close exactly its own zombies.
 *
 * Named breakages this catches that no vitest file can:
 *  - the sweep goes blind (label or history-read drift): every restart with
 *    the tab open returns a dead-menu window, the bug the owner lived through;
 *  - the sweep overreaches and closes a tab whose origin still answers: the
 *    user's live harness view, or a recycled port someone else got home on.
 *
 * Everything here goes through the real command, the real served-urls file
 * and real browser tabs, in the real extension host.
 */
import * as assert from 'node:assert/strict'
import * as http from 'node:http'
import * as net from 'node:net'
import { mkdirSync, writeFileSync } from 'node:fs'
import * as path from 'node:path'
import * as vscode from 'vscode'

const BRIDGE_ID = 'System-Sciences.dsh-vllm-bridge'
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

function labels(): string[] {
  return vscode.window.tabGroups.all.flatMap((group) => group.tabs.map((tab) => tab.label))
}

function plantHistory(urls: string[]): void {
  const repoRoot = vscode.extensions.getExtension(BRIDGE_ID)?.extensionUri.fsPath
  assert.ok(repoRoot, 'the bridge must be loaded (development path)')
  const file = path.join(
    repoRoot,
    '.vscode-test',
    'user-data',
    'User',
    'globalStorage',
    BRIDGE_ID,
    'dsh-home',
    'vllmc',
    'served-urls.log',
  )
  mkdirSync(path.dirname(file), { recursive: true })
  writeFileSync(file, urls.join('\n') + '\n')
}

async function openBrowser(url: string): Promise<string> {
  const label = new URL(url).host
  await vscode.commands.executeCommand('workbench.action.browser.open', url)
  const deadline = Date.now() + 15_000
  while (Date.now() < deadline) {
    if (labels().includes(label)) return label
    await sleep(250)
  }
  assert.fail(`no browser tab labeled ${label} appeared for ${url} (tabs: ${labels().join(' | ') || 'none'})`)
}

async function freePort(): Promise<number> {
  const probe = net.createServer()
  await new Promise<void>((resolve) => probe.listen(0, '127.0.0.1', resolve))
  const port = (probe.address() as net.AddressInfo).port
  await new Promise<void>((resolve) => probe.close(() => resolve()))
  return port
}

describe('stale embedded tab sweep', () => {
  it('closes a stale harness tab whose origin answers nothing', async () => {
    const label = `127.0.0.1:${await freePort()}`
    const url = `http://${label}/stale-probe?token=dead`
    plantHistory([url])
    await openBrowser(url)
    await vscode.commands.executeCommand('dshBridge.sweepStaleTabs')
    const deadline = Date.now() + 20_000
    while (Date.now() < deadline && labels().includes(label)) await sleep(300)
    assert.ok(!labels().includes(label), `the stale harness tab ${label} survived the sweep`)
  })

  it('keeps a harness-history tab whose origin still answers', async () => {
    const server = http.createServer((_req, res) => {
      res.writeHead(200, { 'content-type': 'text/plain' })
      res.end('still home')
    })
    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
    const label = `127.0.0.1:${(server.address() as net.AddressInfo).port}`
    try {
      plantHistory([`http://${label}/`])
      await openBrowser(`http://${label}/`)
      await vscode.commands.executeCommand('dshBridge.sweepStaleTabs')
      await sleep(3000)
      assert.ok(labels().includes(label), `the sweep closed a live tab on ${label}`)
    } finally {
      await new Promise<void>((resolve) => server.close(() => resolve()))
    }
  })
})
