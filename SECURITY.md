# Security policy

## Supported version

Security fixes are applied to the current default branch.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature rather than opening a public
issue. Include the affected component, a reproducible example, and the likely impact.

Do not include credentials, private procurement information, or unnecessary personal data
in a report.

## Security boundaries

ContractDelta is a static public-data application. The production site has no authentication,
cookies, user accounts, database, or server-side request path. Scheduled ingestion runs in
GitHub Actions with read access to the public AusTender API, write access to non-identifying
public update status, and a repository-scoped deploy key for the separate private data
repository.

The source client accepts pagination links only from `https://api.tenders.gov.au` and enforces
bounded dates, pages, amendment selection, backfill windows, timeouts, and retries.

Source text is rendered through Astro's escaping boundary. CSV text that could be interpreted
as a spreadsheet formula is prefixed safely, while the JSON evidence retains the exact
normalised value. The site also applies a restrictive content policy and referrer policy.
Same-origin connections support prefetched page navigation while cross-origin connections
remain blocked. Every cross-origin link explicitly suppresses referrer information.

Normalised names and descriptions pass a fail-closed scan for high-confidence email,
business-identifier, Australian phone-number, and street-address patterns. Full state,
immutable events, manifests, and checkpoints remain in a private repository. Generated site
data exists only in the deployment runner and static artifact, not public Git history.

The scheduled updater validates every distinct generated source path, then availability-checks
up to 100 recent destinations without following redirects or downloading response bodies.
Definite missing-record responses stop the update. Access controls, rate limits, server errors,
and network failures are reported as indeterminate so temporary source-side blocking does not
masquerade as a broken record.

Workflow actions are pinned to immutable release commits. Dependabot monitors the workflow,
Python, and npm ecosystems, while CI runs Python and npm vulnerability audits.

The private deploy key must be unique to this project, stored only as the
`PRIVATE_DATA_DEPLOY_KEY` repository secret, and granted access only to the private data
repository. It must not be reused as a personal SSH key or broader account credential.

## Hosting limitations

GitHub Pages controls the HTTP response headers. The project therefore cannot set headers such
as `X-Content-Type-Options` or `Permissions-Policy` at the hosting layer. A content security
policy is supplied in the static document, but response-header enforcement would require a
different static host.
