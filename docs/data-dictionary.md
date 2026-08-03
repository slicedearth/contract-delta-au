# Data dictionary

## Contract version

| Field | Meaning |
|---|---|
| `contract_id` | Stable parent Contract Notice ID, such as `CN4260041` |
| `notice_id` | Parent or explicit amendment ID, such as `CN4260041-A1` |
| `source_release_id` | OCDS release identifier used for provenance and deduplication |
| `source_modified_at` | UTC timestamp reported by the source release |
| `official_record_url` | Human-readable AusTender Contract Notice or amendment page; falls back to an official CN search when an exact page identifier is unavailable |
| `source_url` | Machine-readable AusTender OCDS JSON endpoint for the Contract Notice |
| `source_hash` | SHA-256 of the privacy-minimised normalised contract fields |
| `agency_name` | Source party with the `procuringEntity` role |
| `supplier_name` | Source party with the `supplier` role, or `Supplier not reported` when that field contains a contact or address marker |
| `description` | Source contract description, or `Contract description not published` when that field contains a contact or address marker |
| `reported_value` | Maximum contract-life value reported by AusTender, normally AUD |
| `contract_start_date` | Source contract start date on the Canberra calendar |
| `contract_end_date` | Source contract end date on the Canberra calendar |
| `category_code` | Primary source UNSPSC classification code |
| `procurement_method` | Source procurement method description |

## Change event

| Field | Meaning |
|---|---|
| `event_id` | Deterministic SHA-256 of contract, after-release, and field |
| `detected_at` | Modification timestamp of the after-release |
| `field_name` | Normalised field that changed |
| `old_value` / `new_value` | Exact normalised before-and-after values |
| `absolute_change` | New minus old reported value |
| `percentage_change` | Value difference divided by old value, multiplied by 100 |
| `duration_change_days` | New date minus old date in calendar days |
| `before_release_id` / `after_release_id` | OCDS releases supporting the comparison |
| `before_source_hash` / `after_source_hash` | Normalised evidence hashes |
| `official_record_url` | Human-readable AusTender page for the after-release notice |
| `source_url` | Machine-readable AusTender OCDS JSON endpoint for the Contract Notice |

## Excluded source fields

Contact names, phone numbers, email addresses, ABNs, street addresses, and postal addresses are
not required for contract-change analysis and are not retained.

The source manifest records `supplier_names_redacted` and `descriptions_redacted`, the numbers
of release versions whose supplier or description field was replaced during the latest run.
Supplier placeholders appear on the affected contract but are excluded from supplier
summaries. Description placeholders state that the source text was not retained or published.

## Collection coverage

| Field | Meaning |
|---|---|
| `mode` | Whether the run processed supplied releases, a saved fixture, or a bounded amendment selection |
| `selection_method` | Plain-language description of the deterministic coverage rule |
| `query_start` / `query_end` | UTC boundaries of the latest-modified interval |
| `max_amended_contracts` | Maximum amendment contracts retained from that interval |
| `amended_contracts_discovered` | Distinct explicit amendment contracts found before selection |
| `amended_contracts_selected` | Distinct amendment contracts selected for processing |
| `amended_contracts_skipped` | Discovered contracts outside the configured cap |

These fields describe the most recent collection interval in the source manifest and public
dashboard. Historical checkpoint files add cumulative window and event counts for a specified
range.

## Public update status

`site/src/data/update-status.json` is the only production update record committed to the public
repository. It contains retrieval and latest-source timestamps, private-state contract and
event counts, collection coverage, non-identifying privacy-redaction counts, and the
corresponding private revision. It deliberately
excludes contract IDs, notice IDs, agency names, supplier names, descriptions, values, source
URLs, release IDs, and evidence hashes.
