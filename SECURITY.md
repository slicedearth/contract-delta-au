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
GitHub Actions with read access to the public AusTender API and write access only to the
repository contents required for derived data updates.

The source client accepts pagination links only from `https://api.tenders.gov.au` and enforces
bounded dates, pages, timeouts, and retries.

Source text is rendered through Astro's escaping boundary. CSV text that could be interpreted
as a spreadsheet formula is prefixed safely, while the JSON evidence retains the exact
normalised value. The site also applies a restrictive content policy and referrer policy.
Every cross-origin link explicitly suppresses referrer information.

The scheduled updater checks all distinct generated source destinations without following
redirects or downloading response bodies. Definite missing-record responses stop the update.
Access controls, rate limits, server errors, and network failures are reported as indeterminate
so temporary source-side blocking does not masquerade as a broken record.

Workflow actions are pinned to immutable release commits. Dependabot monitors the workflow,
Python, and npm ecosystems, while CI runs Python and npm vulnerability audits.

## Hosting limitations

GitHub Pages controls the HTTP response headers. The project therefore cannot set headers such
as `X-Content-Type-Options` or `Permissions-Policy` at the hosting layer. A content security
policy is supplied in the static document, but response-header enforcement would require a
different static host.
