# Architecture

ContractDelta is a scheduled data pipeline and a static website. It deliberately avoids an
always-running service.

## Components

1. `AusTenderClient` retrieves latest-modified OCDS release packages, follows same-origin
   cursor links, ranks explicit amendment contracts deterministically, and hydrates parent
   history for a bounded selected set.
2. `normalise_release` reduces each source release to analysis fields, replaces supplier and
   description fields containing contact or address markers, and excludes other unnecessary
   personal data.
3. `compare_versions` is a pure function that creates deterministic field-level events.
4. `process_releases` merges validated versions in a private data checkout without allowing old
   releases to roll current state backwards.
5. `build_site_data` creates compact dashboard JSON, per-contract evidence JSON, and a CSV
   event export.
6. Astro renders static pages from temporary generated assets. The change feed is divided into
   50-event static pages with prefetched client-side navigation and sticky controls. Filters
   load the already-public event export on demand, search the full dataset, paginate matching
   results in groups of 50, and export the complete filtered set. Every event remains reachable
   without an always-running server or a full document reload between result pages.
7. The scheduled update validates every published source path, availability-checks a bounded
   recent sample, and fails on definite missing-record responses.
8. The historical workflow processes limited date windows and records an atomic checkpoint
   after each successful window.
9. A successful scheduled update or historical backfill triggers a fresh deployment after its
   verified private state and non-identifying public status have been committed. Failed data
   workflows do not publish a new site build.
10. A repository-scoped deploy key connects the public workflow to the private data repository.
   Generated dashboard and evidence files exist in the runner and deployment artifact only.

## Trust boundaries

- AusTender JSON is untrusted input and validated before publication.
- Pagination URLs must use HTTPS, the `api.tenders.gov.au` host, and the expected path.
- Date ranges, pagination, amendment selection, backfill windows, retries, and timeouts are
  bounded.
- Source records are never rendered directly as HTML.
- Published cross-origin links suppress referrer information.
- Deployment contains no server runtime. Workflow access uses one scoped deploy-key secret;
  the built site contains no credential.

## State and evidence

The private repository's `data/state/current-contracts.json` retains privacy-minimised versions
and source release IDs. `data/events/change-events.json` is append-only in normal operation.
The manifest records counts, privacy redactions, selection coverage, validation failures,
retrieval time, parser version, source URLs, and hashes of both files. Historical checkpoints
record cumulative discovered, selected, skipped, and added-event counts without claiming
exhaustive collection.

Static evidence bundles include the source release IDs, normalised hashes, before and after
values, and the primary OCDS record URL. They are generated for each deployment and do not
enter public Git history. They are evidence aids, not replacements for the source.
