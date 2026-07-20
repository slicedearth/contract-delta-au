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
