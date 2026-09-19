# Public research journal

This is a sanitized decision log, not the original execution journal. Private
statement IDs, job IDs, credentials, source contents, and raw receipts are not
published. Dates below refer to the study's recorded experiment dates.

## 2026-09-17 — baseline and measurement corrections

Froze the hotel-facts contract and retained Precision v2.1 with citations.
Established ten-document / 236-page managed and native reference artifacts.
Managed parsing itself missed some item-specific symbols; generated diagram
descriptions were not reliable truth. Page coverage and lexical overlap did
not prove extraction completeness. Rejected inherited peak-RSS measurements
and separated native-stage timing from full-pipeline latency.

## 2026-09-18 — reusable controls and negative outcomes

Added scope-bound cache decisions, original-page provenance derivation,
complete-page assembly, and exact-output native TextPage reuse. Kept raw
responses unchanged. Native reuse yielded subsecond gains on the corpus;
those are not managed pipeline savings.

Some targeted page improvements were achieved, while full document and
full-corpus completeness remained unresolved. Whole-page text retained tokens
but misassociated column contents. More detailed inputs and chunking often
increased cost or latency. Previously inspected examples ceased to be holdouts.

## 2026-09-18–19 — Jev ablations and doc-router analysis

Compared managed-all, fixed rules, document Jev, and page Jev. Recommendations
did not establish work avoided. Shared identical extraction work across Jev
and no-Jev arms instead of duplicating inference.

E24 compact shared-state prompts reduced input tokens by 32.48%, but changed
26/236 decisions. Recorded both the cheaper router and policy drift.

E23 used exactly four separately authorized source-bearing verifier requests.
Three of five error signals were flagged, with two missed signals and zero
false alarms among three negative labels. No automatic acceptance, retry,
or fallback extraction occurred. The permission is exhausted.

Reviewed doc-router at a pinned commit without building or running it. Its
selective-OCR architecture is useful, but the reported gain missed nine
needed-OCR pages. Chose selective Databricks parsing and strict reassembly
as the next candidate, not its external OCR integration or retry defaults.

## 2026-09-19 — E25 saved-artifact rehearsal and publication

Completed all five arms across all ten documents: 50 cases / 36 unique bundles,
complete 236-page inventories, no PDF reads, no AI calls. Sixteen remote
synthetic tests passed. The 19.381964-second rehearsal exposed native/managed
discrepancies and omitted figure-description evidence, not accepted omissions
or measured savings. Live selected-page parsing was not dispatched.

Published an allowlisted snapshot at the user's request. The included offline
suite has 93 tests. Source data, raw evidence, private deployment settings, and
credentials remain excluded. No production deployment or additional hosted
source-text request is authorized by this publication.

Next: independently justify safe-to-skip pages, validate selected-parser page
mapping, evaluate complete downstream quality on unseen layouts, and measure
matched end-to-end economics. The research objective remains unfinished.

## 2026-09-19 — later evidence and publication update

E26 retained requested original page identities across five selected pages
and reassembled all 30 physical pages. A frozen reference error was recorded
separately, and a missing visual detail prevents quality acceptance. Most of
the observed 407.769-second statement duration was warehouse queue time,
not an isolated parser measurement.

E27 corrected HTML-sensitive lexical diagnostics on matched eligible pages.
Three projection failures remain unknown. Lower diagnostic counts are not
better extraction or permission to skip managed parsing.

E28 restored all ten saved parser envelopes exactly. Complete serialized
bytes fell 3.7440%, versus 13.8741% for content characters. Published the
unchanged deterministic codec and its 21 synthetic tests, not document data.
The public offline suite now has 114 tests. No inference economics or
incremental Jev benefit follows from reversible serialization.

E29's four fully synthetic Precision inputs completed. All return expected
names and citation kinds, but none passes the full narrow automated gate.
Published only preliminary aggregates with explicit unreviewed-failure
caveats; no semantic acceptance or compaction advantage is claimed. The
retained results need diagnosis before further inference.

Rechecked retained evidence consistency without rerunning experiments. The
public snapshot remains allowlisted; original inputs, raw responses, private
receipts, and infrastructure identifiers remain excluded. TypeSafe guidance
continues to keep typed outputs and confidence separate from truth. The
Databricks guidance supports reusing persisted outputs, not duplicate calls.
No new hosted source-bearing request, deployment, or AI experiment was made
for this update. The broader optimization objective remains unfinished.
