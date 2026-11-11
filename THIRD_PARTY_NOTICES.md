# Third-party notices

Rilo source is licensed under Apache-2.0; see [LICENSE](LICENSE). Original synthetic research corpus passages are offered under CC0-1.0; see [CC0 text](docs/licenses/CC0-1.0.txt). Names, organizations, events and `.example` source URLs in that corpus are fictional evaluation material.

## Bundled frontend assets and libraries

Promptfoo 0.125.1 is reused as the actual task assertion engine under MIT. Its
React `TruncatedText` component was copied from the same tag and adapted for Rilo's
theme, semantic toggle button and expansion state. Copyright (c) Promptfoo 2025.
The full notice is retained in [promptfoo-MIT.txt](docs/licenses/promptfoo-MIT.txt).
Source: https://github.com/promptfoo/promptfoo/tree/0.125.1

Rilo's surrounding matrix, ingestion and worker adapters are Rilo code. The full
Promptfoo product UI and cloud services are not bundled. Runtime dependency
versions are locked in `backend/rilo/promptfoo_runtime/package-lock.json`.

| Component | Selected version | License |
| --- | --- | --- |
| React / React DOM | 19.3.1 | MIT |
| Lucide React icons | 1.70.0 | ISC |
| Inter through Fontsource | 5.3.0 | SIL OFL 1.1 |
| JetBrains Mono through Fontsource | 5.3.0 | SIL OFL 1.1 |
| Vite | 8.3.6 | MIT |
| TypeScript | 6.0.3 | Apache-2.0 |
| Playwright | 1.65.0 | Apache-2.0 |
| axe-core / axe Playwright | 4.14.0 | MPL-2.0 |

Font copyright and full license notices are retained in [Inter-OFL.txt](docs/licenses/Inter-OFL.txt) and [JetBrains-Mono-OFL.txt](docs/licenses/JetBrains-Mono-OFL.txt). Fonts are self-hosted by the frontend build and are not fetched from an external font service at runtime.

## Backend and optional local services

| Component | Selected version | License |
| --- | --- | --- |
| FastAPI | 0.162.2 | MIT |
| Pydantic | 2.14.3 | MIT |
| LangGraph | 1.2.20 | MIT |
| HTTPX | 0.28.1 | BSD-3-Clause |
| Uvicorn | 0.54.0 | BSD-3-Clause |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| pypdf | 6.21.4 | BSD-3-Clause |
| ReportLab | 4.5.1 | BSD, package license.txt |
| defusedxml | 0.7.1 | PSF |
| certifi | 2026.10.23 | MPL-2.0 |
| Pillow (ReportLab dependency) | 13.0.0 | MIT-CMU |
| Bifrost gateway | v2.5.0, project-local download | Apache-2.0 |
| Ollama | Existing external local installation | MIT; model licenses are separate |

Exact transitive versions and distribution hashes are in `uv.lock` and `frontend/package-lock.json`. The local license metadata review found declared licenses or license classifiers for all installed Python packages. Node dependency notices are supplied with installed packages; distribution should retain their required notices. Dependency audits check known advisory data and do not constitute a legal or security certification.

Bifrost and model weights are installed in ignored local locations and are not vendored in this repository. The setup helper records the official artifact URL and its SHA256; Bifrost's upstream license applies to redistribution. Tavily is a service under its own terms. Application uploads, private source objects, conversations and credentials stay in ignored local storage. The synthetic benchmark reports and explicitly prepared KYRO example below are the published evidence set.

## KYRO example report

The prepared `docs/ui-evidence/kyro-recovery-2026-11-10.*` reports include source
excerpts from [Gauravwakle96/KYRO](https://github.com/Gauravwakle96/KYRO) at commit
`a03f97ded1f5da474cf16eefe08afec1b5133e07`. KYRO is MIT-licensed; its copyright and
permission notice are retained in [KYRO-MIT.txt](docs/licenses/KYRO-MIT.txt).
Those third-party excerpts retain their license and are not relicensed as Rilo code
or synthetic CC0 fixtures. The report contains model interpretations, which are not
claims by KYRO's author or independently validated security conclusions.

The installed Qwen model is an independently downloaded artifact governed by its model license. Rilo does not grant rights to third-party models, provider brands, or retrieved publications. The working name has not been reviewed for trademark/domain availability.
