# Data dictionary

## Contract version

| Field | Meaning |
|---|---|
| `contract_id` | Stable parent Contract Notice ID, such as `CN4260041` |
| `notice_id` | Parent or explicit amendment ID, such as `CN4260041-A1` |
| `source_release_id` | OCDS release identifier used for provenance and deduplication |
| `source_modified_at` | UTC timestamp reported by the source release |
| `source_hash` | SHA-256 of the privacy-minimised normalised contract fields |
| `agency_name` | Source party with the `procuringEntity` role |
| `supplier_name` | Source party with the `supplier` role |
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
| `source_url` | Primary AusTender OCDS endpoint for the Contract Notice |

## Excluded source fields

Contact names, phone numbers, email addresses, ABNs, street addresses, and postal addresses are
not required for contract-change analysis and are not retained.
