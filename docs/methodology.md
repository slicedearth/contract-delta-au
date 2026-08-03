# Methodology

## Observation model

ContractDelta separates four layers:

1. **Source fact:** a field reported in an AusTender OCDS release.
2. **Calculated fact:** a deterministic difference, percentage, or day count.
3. **Context:** the agency, supplier, category, amendment number, and contract period.
4. **Interpretation:** left to the researcher after inspecting primary records and other
   evidence.

The application does not calculate a corruption, fraud, risk, or suspicion score.

## Collection coverage

Each source interval identifies contracts tagged as explicit amendments. ContractDelta keeps
the latest candidate per contract, ranks candidates by current reported value, and uses source
modification time, contract ID, and release ID as deterministic tie-breakers. Only the highest
ranked configured number is hydrated and processed.

The source manifest and public data page report the interval, selection method, cap, and
discovered, selected, and skipped contract counts. Skipped contracts are outside the
collection boundary. Their omission is not evidence that they were unchanged or unimportant.

Historical collection uses inclusive date ranges of no more than 366 days. It divides a range
into bounded windows and writes a checkpoint after each successful window so work can resume
without silently skipping a failed interval.

## Version order

AusTender parent notices use identifiers such as `CN123456`. Amendments use explicit suffixes
such as `CN123456-A1` and `CN123456-A2`. ContractDelta uses the numeric suffix as the primary
sequence because multiple releases can share the same modification timestamp. The source
timestamp and release ID provide deterministic tie-breakers.

## Normalisation

- amounts are parsed as two-decimal `Decimal` values
- contract dates are converted to the Canberra calendar date before comparison
- source modification timestamps remain UTC
- whitespace and HTML entities are normalised
- empty values become null
- party letter case is preserved
- only the primary contract and primary UNSPSC classification are analysed
- supplier fields containing high-confidence email, labelled business-identifier, Australian
  phone-number, or street-address patterns become `Supplier not reported`
- descriptions containing the same patterns become `Contract description not published`
- the same patterns in agency, title, and procurement-method fields stop publication

Formatting-only changes do not produce events. Null-to-value and value-to-null transitions do.

## Field calculations

Value change:

```text
absolute change = current reported value - previous reported value
percentage change = absolute change / previous reported value × 100
```

No percentage is calculated when the previous value is zero or absent.

Date change:

```text
duration change = current date - previous date, in calendar days
```

## Data quality

Publication stops if more than 2% of unique releases fail validation, if every release fails,
if pagination exceeds its configured bound, or if the source provides an unsafe next-page URL.
Temporary source failures are retried. A temporarily absent contract never deletes local
history.

Publication also stops if the source publisher or data licence changes unexpectedly. That
requires a manual licensing and attribution review before any new derived data is published.

The manifest makes partial validation failures visible even when they remain below the stop
threshold.

Published events distinguish the human-readable official Contract Notice from the
machine-readable OCDS JSON source. When the source does not expose a valid page identifier,
the official-record link falls back to an AusTender search for the parent CN ID.

Every distinct published official-record and OCDS JSON path is validated. Destinations outside
the approved source paths fail before any request, including paths beyond the availability
sample. The weekly update checks up to 100 recent destinations. For source responses, only a
definite `404` or `410` is treated as broken. Redirects, access controls, rate limits, server
errors, and network failures are recorded as indeterminate because they do not prove that a
public record is missing.

CSV exports neutralise text that spreadsheet applications could otherwise interpret as a
formula. JSON evidence preserves the exact normalised text.

Durable state, immutable events, manifests, and backfill checkpoints are stored in a private
repository. Public JSON, CSV, and per-contract evidence files are generated only for the
static deployment artifact and are not committed to public Git history. This limits
historical persistence in source control, but it does not make information displayed by the
public site private.

## Limitations

- A modification can be a correction rather than a contractual variation.
- Reported contract value is not annual or realised expenditure.
- The source can publish several historical amendments at one timestamp.
- Supplier naming is source-reported and may change without a legal-entity change.
- Category codes describe a primary classification, not every good or service supplied.
- A source record and surrounding procurement documentation remain necessary for context.
- Collection is capped per interval and favours contracts with higher current reported values.
- Supplier names can identify sole traders or other individuals even when contact fields are
  excluded; do not enrich or republish unnecessary personal information.
