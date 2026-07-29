# Legal and licensing notes

This document records practical publication safeguards for the project. It is not legal
advice. Obtain Australian legal advice before relying on the project for a contentious
publication, a commercial service, or a decision affecting a person or organisation.

## Source data licence

The Australian Government Department of Finance publishes the
[AusTender Contract Notice dataset](https://www.data.gov.au/data/dataset/historical-australian-government-contract-data)
under the [Creative Commons Attribution 3.0 Australia licence](https://creativecommons.org/licenses/by/3.0/au/).
That licence permits reuse and adaptation, subject to requirements that include attribution,
a licence link, an indication of changes, preservation of relevant notices, and no implication
of sponsorship or endorsement.

ContractDelta meets that publication model by:

- naming the Australian Government Department of Finance as the attribution party
- linking the source record and CC BY 3.0 AU licence
- marking outputs as selected, privacy-minimised, normalised, and compared adaptations
- carrying attribution fields in downloadable JSON and CSV events
- stating that the project is independent and not endorsed by the Australian Government
- stopping automated publication if the reported source publisher or licence changes

The top-level MIT Licence applies to original application code and project documentation. It
does not relicense AusTender-derived records in the private data repository, generated
deployment artifacts, or public fixtures. Those materials remain subject to the source CC BY
3.0 AU licence and the attribution in `NOTICE`.

## Privacy and data minimisation

Public availability does not make every secondary use of personal information appropriate.
The Office of the Australian Information Commissioner notes in its
[APP 3 guidance](https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines/chapter-3-app-3-collection-of-solicited-personal-information)
that publicly available personal information still requires attention to purpose and
reasonable expectations.

ContractDelta retains agency and supplier names because they are necessary to analyse public
contracts. A supplier name can identify a sole trader or other individual. The pipeline
therefore excludes contact names, phone numbers, email addresses, ABNs, and street and postal
addresses, and it does not enrich records with data from other sources. Supplier fields
containing high-confidence contact or address markers are replaced with
`Supplier not reported`. Matches in other retained fields remain fail-closed and cannot enter
durable state or a deployment artifact.

Full state and history remain in a private repository. Public deployment artifacts still make
the selected contract facts available to site visitors, so repository separation is a
retention and access-control safeguard rather than de-identification.

Do not place sensitive details in a public issue. Use GitHub's private vulnerability reporting
channel for a sensitive security or privacy report. A source correction should be checked
against the primary AusTender record before any local change is made.

## Defamation and reputational risk

Australian publication risk can arise from an unsupported allegation or implication, not only
from an explicit accusation. ContractDelta reports source and calculated facts and does not
label a contract, agency, or supplier corrupt, fraudulent, suspicious, or high risk.

Anyone publishing an investigation based on these outputs should inspect the primary record,
seek surrounding documents, explain uncertainty, avoid treating rankings as culpability, and
give affected parties a fair opportunity to provide context.

## Names, marks, and endorsement

“AusTender” and Australian Government agency names are used descriptively to identify the
source. The project does not use government crests or logos and states that it is independent.
The ContractDelta AU name has not received a formal trade mark clearance; conduct an
[Australian Trade Mark Search](https://search.ipaustralia.gov.au/trademarks/search/quick)
and obtain advice before commercial branding or registration.

## Ongoing review

Source terms, licences, privacy law, publication law, and hosting policies can change. Review
the current primary-source terms before expanding the dataset, adding personal information,
introducing alerts or profiles, monetising the service, or moving beyond factual contract
change reporting.
