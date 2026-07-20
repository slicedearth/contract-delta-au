# Architecture

ContractDelta is a scheduled data pipeline and a static website. It deliberately avoids an
always-running service.

## Components

1. `AusTenderClient` retrieves latest-modified OCDS release packages, follows same-origin
   cursor links, and hydrates a parent history for each amendment.
2. `normalise_release` reduces each source release to analysis fields and removes contact and
   address data.
3. `compare_versions` is a pure function that creates deterministic field-level events.
4. `process_releases` merges validated versions without allowing old releases to roll current
   state backwards.
5. `build_site_data` creates compact dashboard JSON, per-contract evidence JSON, and a CSV
   event export.
6. Astro renders static pages. Browser JavaScript is limited to filtering and client-side CSV
   export of already-public data.
7. The scheduled update checks bounded, validated source destinations and fails on definite
   missing-record responses.

## Trust boundaries

- AusTender JSON is untrusted input and validated before publication.
- Pagination URLs must use HTTPS, the `api.tenders.gov.au` host, and the expected path.
- Date ranges, pagination, retries, and timeouts are bounded.
- Source records are never rendered directly as HTML.
- Published cross-origin links suppress referrer information.
- Deployment contains no secrets and no server runtime.

## State and evidence

`data/state/current-contracts.json` retains privacy-minimised versions and source release IDs.
`data/events/change-events.json` is append-only in normal operation. The manifest records
counts, validation failures, retrieval time, parser version, source URLs, and hashes of both
files.

Static evidence bundles include the source release IDs, normalised hashes, before and after
values, and the primary OCDS record URL. They are evidence aids, not replacements for the
source.
