# Public data boundary

Durable contract state is stored in a separate private repository. This public directory does
not contain contract histories, immutable field events, retrieval manifests, or backfill
checkpoints.

- Source work: AusTender Contract Notice data
- Attribution party: Australian Government Department of Finance
- Source: <https://api.tenders.gov.au/ocds/>
- Licence: [Creative Commons Attribution 3.0 Australia](https://creativecommons.org/licenses/by/3.0/au/)

ContractDelta selects privacy-minimised fields, normalises values and dates, calculates
field-level differences, orders releases, and adds evidence hashes. These are independent
adaptations and are not official Department of Finance calculations.
Static JSON, CSV, and evidence bundles are generated inside the deployment runner rather than
committed here.

The public `site/src/data/update-status.json` file records only retrieval timestamps, counts,
coverage boundaries, and the corresponding private revision. It contains no contract,
supplier, agency, description, or source-record content.

The source-derived data remains subject to CC BY 3.0 AU and is not covered by the repository's
MIT Licence. Preserve the attribution, licence link, adaptation notice, and primary record
links when redistributing it.
