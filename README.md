# ContractDelta AU

**Version control for Australian Government contracts.**

ContractDelta AU monitors public AusTender Contract Notices and records how reported
contract values, dates, suppliers, agencies, descriptions, categories, and procurement
methods change over time.

[View the dashboard](https://slicedearth.github.io/contract-delta-au/) ·
[Read the methodology](docs/methodology.md) ·
[Inspect the data dictionary](docs/data-dictionary.md) ·
[Review legal and licensing notes](docs/legal-and-licensing.md)

## What it shows

- reproducible before-and-after comparisons
- amendment timelines ordered by AusTender's explicit `-A#` identifiers
- agency and supplier summaries
- direct links to official AusTender records and OCDS JSON
- downloadable JSON evidence and CSV change data
- source hashes, retrieval manifests, and quality-stop checks

ContractDelta does not identify fraud or misconduct. Changes are research leads that
require context and verification from primary sources.

> **Data interpretation:** “reported contract value” is used throughout. AusTender values
> describe the reported maximum value over the life of a contract; they are not annual
> government expenditure.

## How it works

```text
AusTender OCDS API
        │
        ▼
fetch cursor pages → hydrate amendment histories → validate and minimise
        │
        ▼
normalise amounts, dates, whitespace, parties, categories, and notice IDs
        │
        ▼
compare versions → append immutable field events → hash evidence
        │
        ▼
generate static JSON, CSV, contract timelines, and Astro pages
        │
        ▼
GitHub Actions → GitHub Pages
```

The pipeline follows the API's opaque cursor links with a strict same-origin check. When a
date-range page contains an amendment, it fetches that contract's parent history so a new
repository can still calculate the real before value. Contacts, email addresses, ABNs, and
street addresses are deliberately excluded.

## Local development

Requirements: Python 3.12+ and Node.js 24 LTS. Python 3.14 and npm 12 are used by
automation; Python 3.12 remains the supported compatibility floor.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/contract-delta ingest-fixture tests/fixtures/amended_releases.json

cd site
npm ci
npm run dev
```

Run the checks:

```bash
.venv/bin/ruff check .
.venv/bin/pytest --cov=contract_delta --cov-report=term-missing
.venv/bin/contract-delta check-source-links
cd site && npm run check && npm run build
```

Fetch a live latest-modified window:

```bash
.venv/bin/contract-delta update --from 2026-07-14 --to 2026-07-15
```

Date ranges are capped at 31 days, pagination is capped at 250 pages by default, transient
source failures are retried, and publication stops if validation failures exceed 2%.
The weekly update checks every distinct published source destination. Definite `404` and `410`
responses fail the run, while access controls, rate limits, server errors, and network failures
are reported as indeterminate for manual review.

## Repository layout

```text
src/contract_delta/       typed source client, normalisation, diff, and publication
tests/                    behavioural tests and privacy-minimised public fixtures
data/state/               current normalised contract history
data/events/              immutable field-level events
data/manifests/           retrieval, quality, count, and checksum evidence
site/                     static Astro dashboard
docs/                     architecture, methodology, ethics, and data definitions
.github/workflows/        CI, scheduled updates, and Pages deployment
```

## Automation and cost

The public repository uses standard GitHub-hosted Actions and GitHub Pages. No application
server, database, account system, secret, or paid production API is required. The weekly
updater also supports manual runs and commits only when derived data changes.

Expected recurring hosting cost: **$0** for a public repository using standard runners and
the included static deployment.

Current runtime and dependency choices, including deliberate compatibility constraints, are
recorded in [the dependency policy](docs/dependency-policy.md). Dependabot checks Python,
site, and workflow dependencies each week.

## Primary sources and attribution

- [AusTender OCDS API documentation](https://github.com/austender/austender-ocds-api)
- [Australian Government Contract Notice dataset](https://data.gov.au/data/dataset/historical-australian-government-contract-data/resource/a7f471ad-e085-49b5-bd6b-1b270ea46e99)
- [Contract Notice data dictionary](https://data.gov.au/data/dataset/5c7fa69b-b0e9-4553-b8df-2a022dd2e982/resource/ae4fec2d-e4aa-46b6-baf6-21e4296a62e4/download/contract-notice-dataset.pdf)

AusTender-derived data and fixtures are attributed to the Australian Government Department
of Finance and used under the
[Creative Commons Attribution 3.0 Australia licence](https://creativecommons.org/licenses/by/3.0/au/).
ContractDelta selects, normalises, and compares that material and clearly marks these
adaptations in downloadable outputs. The application source code and original project
documentation are available under the [MIT Licence](LICENSE); the MIT Licence does not
relicense the source-derived data. See [the legal and licensing notes](docs/legal-and-licensing.md)
and [NOTICE](NOTICE) for the full boundary.
