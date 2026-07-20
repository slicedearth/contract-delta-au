# Methodology

## Observation model

ContractDelta separates four layers:

1. **Source fact** — a field reported in an AusTender OCDS release.
2. **Calculated fact** — a deterministic difference, percentage, or day count.
3. **Context** — the agency, supplier, category, amendment number, and contract period.
4. **Interpretation** — left to the researcher after inspecting primary records and other
   evidence.

The application does not calculate a corruption, fraud, risk, or suspicion score.

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

The manifest makes partial validation failures visible even when they remain below the stop
threshold.

## Limitations

- A modification can be a correction rather than a contractual variation.
- Reported contract value is not annual or realised expenditure.
- The source can publish several historical amendments at one timestamp.
- Supplier naming is source-reported and may change without a legal-entity change.
- Category codes describe a primary classification, not every good or service supplied.
- A source record and surrounding procurement documentation remain necessary for context.
