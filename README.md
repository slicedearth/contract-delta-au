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
commit durable state to a private repository
        │
        ▼
generate temporary JSON, CSV, contract timelines, and Astro pages
        │
        ▼
GitHub Actions → GitHub Pages
```

The pipeline follows the API's opaque cursor links with a strict same-origin check. It ranks
explicit amendment contracts by current reported value, then uses deterministic source-time
and contract-ID tie-breakers to retain a bounded set. Each selected contract's parent history
is fetched so a new repository can calculate the real before value. The dashboard publishes
the latest discovered, selected, and skipped counts. This coverage is intentionally not
exhaustive. Contacts, email addresses, ABNs, and street addresses are deliberately excluded.
Supplier fields containing those markers are replaced with `Supplier not reported`.
High-confidence matches in other retained fields stop publication before data can enter private
history or a deployment artifact.

Full state, events, manifests, and checkpoints live in a separate private repository. The
public repository retains source code, privacy-minimised fixtures, and non-identifying update
counts. Production dashboard data and downloads are generated inside the deployment runner
and are never committed to public Git history. The change feed uses 50-event static pages with
prefetched client-side navigation and sticky controls, so every published event remains
browsable without making any one page grow without bound. Filters load the published event
export on demand, search the full dataset, and paginate matching results in the browser.

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
.venv/bin/contract-delta \
  --data-root ../contract-delta-au-data \
  update \
  --from 2026-07-14 \
  --to 2026-07-15
```

Use the production coverage boundary explicitly:

```bash
.venv/bin/contract-delta \
  --data-root ../contract-delta-au-data \
  update \
  --from 2026-07-14 \
  --to 2026-07-15 \
  --amendments-only \
  --max-amended-contracts 20
```

Resume a bounded historical collection in seven-day windows:

```bash
.venv/bin/contract-delta \
  --data-root ../contract-delta-au-data \
  backfill \
  --from 2025-07-20 \
  --to 2026-07-19 \
  --window-days 7 \
  --max-windows 1 \
  --max-amended-contracts 20
```

Backfill progress is written atomically under `data/manifests/` in the selected private data
root. Re-running the same command continues from the next incomplete window. A range is
limited to 366 inclusive days and each invocation processes at most 53 windows.

Date ranges are capped at 31 days, pagination is capped at 250 pages by default, transient
source failures are retried, and publication stops if validation failures exceed 2%.
Every distinct published source path is validated before a request. The weekly update then
availability-checks up to 100 recent destinations. Definite `404` and `410` responses fail the
run, while access controls, rate limits, server errors, and network failures are reported as
indeterminate for manual review.

## Repository layout

```text
src/contract_delta/       typed source client, normalisation, diff, and publication
tests/                    behavioural tests and privacy-minimised public fixtures
site/                     static Astro dashboard
docs/                     architecture, methodology, ethics, and data definitions
.github/workflows/        CI, scheduled updates, and Pages deployment
```

The sibling private checkout contains `data/state/`, `data/events/`, and `data/manifests/`.
`site/src/data/update-status.json` is the only production update record retained publicly; it
contains counts, timestamps, coverage boundaries, non-identifying privacy-redaction totals,
and the corresponding private revision, but no contract, supplier, agency, description, or
source-record content.

## Automation and cost

The public repository uses standard GitHub-hosted Actions and GitHub Pages. No application
server, database, account system, or paid production API is required. A repository-scoped
deploy key is stored as an Actions secret and grants access only to the private data
repository. The weekly updater also supports manual runs, commits durable data privately,
and commits only non-identifying update status publicly. Successful update and backfill runs
then trigger deployment from the latest public and private revisions; failed data workflows do
not publish a new site build.

Expected recurring hosting cost: **$0** for a public repository using standard runners and
the included static deployment. Bounded collection keeps request volume, repository growth,
and static build time predictable.

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
