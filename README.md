# DeepSeek Harness Bridge — run on your own models

> **Two things to know before installing:**
>
> 1. **This is alpha software.** 0.1.x, one developer; the install procedure and the harness are verified end to end on Windows and on Linux (Ubuntu), in local and remote (WSL, SSH) VS Code windows. It will still surprise you; [rough edges reported](https://github.com/fuzzifikation/dsh-bridge/issues) are what makes it a beta.
> 2. **It requires vLLM-Copilot — and that is where you configure your models.** Your servers, models, modes, and personalities all live in the [vLLM-Copilot](https://github.com/fuzzifikation/vLLM-Copilot) extension's settings; VS Code installs it automatically alongside the bridge. This bridge deliberately has no model configuration of its own: no registry configured there, nothing to boot here.

Run the [DeepSeek Harness](https://www.npmjs.com/package/@deepseek-ai/dsh) (dsh) agent loop entirely on your own vLLM or OpenRouter servers. No DeepSeek account, no credential setup, no vendor login. Your models come from that vLLM-Copilot registry, already configured and working in VS Code — and the harness runs on the vLLM-Copilot core, which is where personalities, served-model filtering, sampling configs, and your token totals come from.

You install the extension. It installs a pinned `@deepseek-ai/dsh` into a private runtime directory (`npx` was rejected: a Windows `.cmd` shim handing you whatever version it feels like), supervises `dsh web` with a dedicated `DSH_HOME`, installs the adapter plugin from this repo into it, and writes a snapshot of your vLLM-Copilot registry (servers, models, modes, sampling params, headers, output budgets). Inside the dsh process, the plugin implements dsh-llm's `LlmAdapter` contract and routes every generation through the vLLM-Copilot core, so your model configs, personalities, and usage accounting apply to harness traffic too. dsh itself stays 100% upstream, never forked.

## What lives in this repo

| Artifact | What it is |
|---|---|
| VS Code extension | The marketplace product: detects Node and dsh, offers install, launches and supervises the harness, writes the registry snapshot and overlay config, reports health, hands completed requests to the vLLM-Copilot usage ledger. |
| dsh adapter plugin | A plain Node package with no VS Code imports. Loaded inside the dsh process as a cordis plugin. Implements `LlmAdapter.stream()` and projects every call onto the vLLM-Copilot core request path. |

## Requirements

- Node.js 22+ with `npm` **and** `pnpm` on PATH (npm installs the pinned harness; dsh installs its profile plugins through pnpm, which npm does not ship). The bridge checks all three before the first download and names what is missing — `npm install -g pnpm` is the one-liner that fixes the third.
- The [vLLM-Copilot](https://github.com/fuzzifikation/vLLM-Copilot) extension with at least one working server and model — **required, not a convenience**. VS Code installs it alongside the bridge automatically; the bridge's whole model path runs on its core, so a machine without a registry gets a clear message and no harness. Extra providers *inside* the harness are welcome ([see FAQ](#can-i-add-other-providers-inside-the-harness)); a harness without vLLM-Copilot is not a mode this product has.

## Alpha testing

This extension is in **alpha**: install it directly from the Marketplace, and every later fix arrives as an automatic update. On first run the bridge asks before downloading anything and verifies the prerequisites on your machine. Harness traffic reaches your usage totals with vLLM-Copilot 1.37.1 or newer; with an older companion the bridge still works and holds the records, visibly, until the companion catches up.

## Security model

A pre-publication review (2026-11-11) shaped this section; the honest picture:

- **Everything stays on your machine.** The harness binds a fresh ephemeral port on `127.0.0.1` with a per-boot UI token. The extension listens on loopback only: a control server with a random per-session bearer token, and an embed proxy that refuses any browser request admitting it came from another site. A web page cannot ring the panel's keyboard bridge or ride its session; local tools can, because a process that already runs as you is the same trust domain the harness itself grants them.
- **Secrets stay in the private storage directory** (your registry snapshot with request headers, the generated patch layer with its control token, the pid record with the UI token), written owner-only on POSIX, and tokens are redacted from every log, report, and error sentence. The stale-tab history stores origins only; tokens never land in plaintext files.
- **The agent can run commands in your editor terminal** and read the files you open. That capability is the product, not a hole, and it is the reason to point the harness at workloads you would run yourself: anything you show an agent (repository content, fetched pages) can steer it.
- **Only loopback harness URLs are trusted**, so a hostile or buggy dsh build cannot aim the panel or the health probes at someone else's machine. Uninstall deletes only directories that really resolve inside the bridge's own storage folder; a planted junction gets a refusal, not a recursive delete.

Same-user assumption: anyone who can read your VS Code profile files or plant directories in it already owns your editor.

## Can I add other providers inside the harness?

Yes — **as extra doors, never as a replacement.** The harness is plain dsh, and dsh ships a multi-provider adapter (`@deepseek-ai/dsh-llm-pi-ai`) that the bridge leaves enabled with **zero routes**: nothing phones out until you add one. Models you add this way appear in the same picker, grouped beside "vLLM-Copilot"; the bridge's own provider owns the route name `vllmc`, and dsh refuses colliding route names at load, so the two doors cannot clobber each other.

The verified door is the profile's own patch layer — edit `dsh-home/profiles/vllmc/cordis.patch.yml` (inside the extension's storage directory), **outside** the generated markers, in the space the file itself reserves for you:

```yaml
- name: '@deepseek-ai/dsh-llm-pi-ai'
  config:
    providers:
      my-gateway:
        displayName: My Gateway
        api: openai-completions          # any OpenAI-compatible server
        baseURL: http://192.168.1.10:8080/v1
        apiKeyEnv: MY_GATEWAY_KEY        # a credential reference; no secret in the file
        models:
          - id: my-model
            contextWindow: 131072
```

Routes apply on the next request — no harness restart. Installed pi-ai catalogs (OpenAI, Anthropic, …) are configured the same way, and the harness has a Models settings page too; the patch layer is the path we verified end to end.

The honest boundary: **usage accounting only sees vLLM-Copilot traffic.** The dashboard totals come from the adapter, so pi-ai-routed turns spend tokens you track on your own side. And the registry stays first-class by architecture, not marketing: the harness boots through the vLLM-Copilot core ([Requirements](#requirements)) — providers you add here join a harness that the registry started, and zero-config personalities, served-model filtering, and the token ledger ride that door alone.

## Status

Alpha (0.1.x), one developer. The loop works end to end: your registry becomes the harness's model list, models your servers stopped serving are hidden, the harness opens as a chromeless tab inside VS Code — per-chat tab titles, VS Code chords answering from inside the frame — the agent can call editor tools (diagnostics, open files and diffs, terminal commands, questions back to you), and harness traffic lands in the vLLM-Copilot usage ledger. Windows and Linux (Ubuntu) are verified end to end, in local windows and in remote ones over WSL and SSH (the panel rides the editor's own port forwarding). The design law for this repo (architecture, owner rulings, verification gates) lives in [docs/dsh-bridge-plan.md](docs/dsh-bridge-plan.md), this repo's own since 2026-10-08.

## Documentation

- [docs/ui-ux.md](docs/ui-ux.md) — the surface as it must be: pill, tabs, titles, keyboard, settings, feel-invariants
- [docs/dsh-bridge-plan.md](docs/dsh-bridge-plan.md) — design law: architecture, owner rulings, verification gates
- [docs/plan.md](docs/plan.md) — dated decision journal (history, with the reasoning)
- [docs/licenses.md](docs/licenses.md) — third-party license audit (2026-11-11): what ships, what downloads, what never leaves this machine
- [docs/upstream-issues.md](docs/upstream-issues.md) — open asks to the harness and to VS Code
- [CHANGELOG.md](CHANGELOG.md) — user-facing releases

## License

MIT. Contains no code from other projects; if that ever changes, attribution lands in `THIRD-PARTY-NOTICES.txt`. The full audit — every shipped file accounted for, the runtime-downloaded harness (MIT) separated from what we distribute, and the dev tree bucketed by license ([docs/licenses.md](docs/licenses.md)) — was done file by file before the first Marketplace publication.

DeepSeek is a trademark of its owner, and VS Code is a trademark of Microsoft. Both names appear here only to state what this bridge works with, and the Marketplace icon is original artwork that incorporates neither company's logo: this extension is independent, not affiliated with, endorsed by, or sponsored by either.
