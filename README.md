# DeepSeek Harness Bridge (vLLM, local)

Run the [DeepSeek Harness](https://www.npmjs.com/package/@deepseek-ai/dsh) (dsh) agent loop entirely on your own vLLM or OpenRouter servers. No DeepSeek account, no credential setup, no vendor login. Your models come from your [vLLM-Copilot](https://github.com/fuzzifikation/vLLM-Copilot) registry, already configured and working in VS Code.

You install the extension. It installs a pinned `@deepseek-ai/dsh` into a private runtime directory (`npx` was rejected: a Windows `.cmd` shim handing you whatever version it feels like), supervises `dsh web` with a dedicated `DSH_HOME`, installs the adapter plugin from this repo into it, and writes a snapshot of your vLLM-Copilot registry (servers, models, modes, sampling params, headers, output budgets). Inside the dsh process, the plugin implements dsh-llm's `LlmAdapter` contract and routes every generation through the vLLM-Copilot core, so your model configs, personalities, and usage accounting apply to harness traffic too. dsh itself stays 100% upstream, never forked.

## What lives in this repo

| Artifact | What it is |
|---|---|
| VS Code extension | The marketplace product: detects Node and dsh, offers install, launches and supervises the harness, writes the registry snapshot and overlay config, reports health, hands completed requests to the vLLM-Copilot usage ledger. |
| dsh adapter plugin | A plain Node package with no VS Code imports. Loaded inside the dsh process as a cordis plugin. Implements `LlmAdapter.stream()` and projects every call onto the vLLM-Copilot core request path. |

## Requirements

- Node.js 22+ with `npm` on PATH (the extension installs the pinned harness with it; dsh's own packages require Node 22). The bridge checks both before the first download and names what is missing.
- The [vLLM-Copilot](https://github.com/fuzzifikation/vLLM-Copilot) extension with at least one working server and model

## Alpha testing

This extension ships as a **pre-release**. In VS Code: search "DeepSeek Harness Bridge", then Install dropdown (the arrow next to Install) › "Install Pre-Release Version". Later alpha builds then arrive as automatic updates; "Switch to Release Version" leaves the channel whenever you want out. On first run the bridge asks before downloading anything and verifies the prerequisites on your machine. Harness traffic reaches your usage totals with vLLM-Copilot 1.37.1 or newer; with an older companion the bridge still works and holds the records, visibly, until the companion catches up.

## Status

Alpha (0.1.x pre-release), one developer. The loop works end to end: your registry becomes the harness's model list, models your servers stopped serving are hidden, the harness opens as a chromeless tab inside VS Code — per-chat tab titles, VS Code chords answering from inside the frame — the agent can call editor tools (diagnostics, open files and diffs, terminal commands, questions back to you), and harness traffic lands in the vLLM-Copilot usage ledger. Windows is the tested platform; others are untested. The design law for this repo (architecture, owner rulings, verification gates) lives in [docs/dsh-bridge-plan.md](docs/dsh-bridge-plan.md), this repo's own since 2026-10-08.

## Documentation

- [docs/ui-ux.md](docs/ui-ux.md) — the surface as it must be: pill, tabs, titles, keyboard, settings, feel-invariants
- [docs/dsh-bridge-plan.md](docs/dsh-bridge-plan.md) — design law: architecture, owner rulings, verification gates
- [docs/plan.md](docs/plan.md) — dated decision journal (history, with the reasoning)
- [docs/upstream-issues.md](docs/upstream-issues.md) — open asks to the harness and to VS Code
- [CHANGELOG.md](CHANGELOG.md) — user-facing releases

## License

MIT. Contains no code from other projects; if that ever changes, attribution lands in `THIRD-PARTY-NOTICES.txt`.

DeepSeek is a trademark of its owner, and VS Code is a trademark of Microsoft. Both names appear here only to state what this bridge works with, and the Marketplace icon is original artwork that incorporates neither company's logo: this extension is independent, not affiliated with, endorsed by, or sponsored by either.
