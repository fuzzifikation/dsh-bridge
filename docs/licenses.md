# Third-party licenses

Audited 2026-11-11 before the first Marketplace publication, file by file and
package by package, the same way vLLM-Copilot's was. The claim this document
defends is in the LICENSE file: MIT, no third-party code inside.

## What the platform requires (researched, not guessed)

Researched against the primary sources the same day: the VS Code
[extension manifest reference](https://code.visualstudio.com/api/references/extension-manifest),
the [publishing guide](https://code.visualstudio.com/api/working-with-extensions/publishing-extension),
and the `vsce` source shipped in this repo's own `node_modules`. What an
extension is actually supposed to provide:

1. **A `license` declaration** in `package.json`. The manifest reference maps it to the Marketplace's License link; npm's rule (which the docs defer to) is an SPDX identifier, with `"SEE LICENSE IN <file>"` reserved for licenses too custom to name. We declare `"MIT"` — the same shape the published, audited vLLM-Copilot extension uses.
2. **A `LICENSE` file at the extension root.** `vsce` enforces this: packaging *fails* without a license file unless you pass `--skip-license` (its own `--help`, measured in our installed copy). Ours packages as `extension/LICENSE.txt`.
3. **The license embedded in the package manifest.** Measured in our built vsix, not assumed: `extension.vsixmanifest` carries `<License>extension/LICENSE.txt</License>` plus an addressable `Content.License` asset, so the gallery and the extension details page link straight to the text. (Notably this happens from the plain `MIT` field too — recent `vsce` finds the root LICENSE either way.)
4. **Rights to everything shipped, and compliance with each bundled license.** The Marketplace Terms of Use make the publisher responsible for the content's licensing; there is **no mandated notices file** — third-party attribution is owed per license (MIT wants the copyright line preserved; Apache-2.0 wants its notice kept), and the ecosystem convention is `THIRD-PARTY-NOTICES.txt`-style bundling *when third-party code ships*. Nothing here does, so nothing is owed; the README already promises the notice file the day that changes.
5. **Runtime-downloaded code is its own product.** dsh arrives from the user's npm with its own LICENSE files in its own tree (visible: hundreds of per-package MIT files inside its `node_modules`) — delivered by npm under npm's rules, exactly like any language package manager, not by our vsix.

Point by point: compliant, with the tooling's own output as the evidence.

## What ships in the .vsix — 44 files, all ours

Every file the Marketplace distributes was listed (`tar -tf dsh-bridge-0.1.3.vsix`)
and accounted for: `out/**` and `shared/**` compile from this repo's TypeScript,
`plugin/**` is this repo's hand-written dsh plugin, `resources/` and
`docs/images/` are the owner's original artwork (pill font generated from
`docs/images/pill_whale.svg` by `scripts/build-pill-font.py`), plus README,
CHANGELOG, LICENSE, manifests. No library, no vendored code, no copied source:
a header sweep for `Copyright` / `Licensed under` / `SPDX` / `All rights reserved`
across every tracked text file finds no third-party notice because there is
nothing to notice. **`dependencies` in package.json is empty** — the
zero-runtime-dependency rule means the shipped product has no license tree at
all. Obligations carried to users: our own MIT text, which ships as
`LICENSE.txt` inside the package.

## What the extension downloads at runtime — not redistribution

The harness itself (`@deepseek-ai/dsh`) is fetched by npm into the user's own
directory, from the user's own npm, under **MIT** (verified via the registry:
repository `github.com/deepseek-ai/deepseek-harness`, pinned version 0.2.2-rc.1
is certified in `config/dsh.json`). The bridge stages its own plugin files into
that installation and applies `plugin/cordis.patch.yml` to the user's own copy;
neither action copies third-party code into anything we distribute. dsh's own
dependency tree is its license story, delivered under its own MIT terms with
the package.

## Build-time and dev-time — nothing here reaches a user

`npx vsce package` assembles the vsix from files already listed; the tools that
produced them run on the author's machine only. The entire dev tree was walked
(330 installed packages, `temp/license-scan.mjs`) and bucketed by declared
license:

| License | Count | Notes |
| --- | --- | --- |
| MIT | 263 | typescript tooling aside, test and build plumbing |
| ISC | 30 | npm-internal plumbing |
| BSD-3-Clause / BSD-2-Clause | 12 | permissive |
| BlueOak-1.0.0 | 9 | permissive (ISC-shaped, ISA-processed) |
| Apache-2.0 | 5 | includes `typescript` |
| Artistic-2.0 | 5 | editorjs-adjacent tooling |
| Python-2.0 | 1 | `argparse` (npm port) |
| MIT OR GPL-3.0-or-later | 1 | `jszip`, disjunctive: the MIT option is the one taken |
| MIT AND Zlib | 1 | `pako`, both permissive |
| 0BSD | 1 | `tslib` |
| proprietary | 1 | `@vscode/vsce-sign` (Microsoft) — runs only as part of the publish toolchain on the author's machine; never shipped, never a user's runtime |

Font pipeline: `fonttools` (MIT) and `brotli` (MIT) rasterize the owner's SVG
into `resources/dsh-bridge-icons.woff2`; their licenses cover the tools, not
the output, and the output is original outlines either way.

## Names and art

DeepSeek is a trademark of its owner; VS Code, Azure DevOps, and the
Marketplace belong to Microsoft; Codicons are referenced by icon *name* through
the VS Code API (an API call, no file shipped). The whale, the pill font, and
the Marketplace icon are the owner's original work. The README says the
affiliation sentence the trademark law wants: independent, not affiliated,
endorsed, or sponsored.

## Conclusion

The only license that travels inside the product is MIT — ours. No NOTICE
file is required by anything in the tree (Apache dev deps would want one only
if redistributed, and they are not). If a future version vendors third-party
code, this document becomes `THIRD_PARTY_NOTICES`-adjacent and the README
clause already promises that.
