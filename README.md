# Databricks + Jev PDF Lab

Research prototypes for lowering PDF extraction cost and latency without
relaxing completeness, exact values, provenance, or Databricks Precision Mode.

**Current result: no quality-equivalent, end-to-end Jev payoff demonstrated.**
The repository publishes reusable code, synthetic tests, aggregate findings,
and failures—not a production router or an accepted hotel-facts dataset.

## What is here

- Metadata-only Jev routing, compact shared-state requests, strict response
  validation, and a single-attempt transport that retains ambiguous outcomes.
- Bounded concurrent request scheduling with durable round markers, no automatic
  replay, and explicit question-to-page binding independent of response order.
- Exact-output native TextPage reuse, page/region assembly, provenance checks,
  and scope-bound cache decisions.
- A selective-parsing rehearsal preserving physical pages, native geometry,
  managed elements, cross-page context, and unresolved review states.
- Reversible table-wrapper compaction with exact round-trip checks and
  original-content fallback; this is not a validated extractor input contract.
- Citation interval unions that preserve uncited gaps, and annotation-preserving
  compaction with synthetic regression tests; neither proves semantic support.
- Source-bound inline-price recovery into separate review-required shadow outputs,
  preserving exact literals, existing fields, and inherited citation IDs.
- Schema-wide field inventory that distinguishes missing, null, empty, and
  populated fields, with literal citation diagnostics but no semantic acceptance.
- Reversible execution of supplied, reviewed field selections with source/schema
  hash guards and existing citations; no automatic semantic discovery or acceptance.
- Field-only composition of retained cited responses, preserving untouched fields,
  exact input text, citation namespaces, annotation origins, and inverse restoration.
- Source-only table-scope candidates with exact spans and explicit abstention;
  layout hypotheses remain separate from semantic ownership and acceptance.
- Chained projection lineage that preserves the exact parent derivation and
  inverse restoration, without relabelling edits as service-generated evidence.
- Exact row-level repair excerpts with retained parent context, origin labels,
  and explicit omissions; supplied selections are not automated semantic routing.
- Parent-conditioned composition of retained donor markers, with exact source
  wording, existing citation spans, origin labels, and reversible lineage.
- Exact span-recipe compilation for SQL-native evidence reordering, with
  complete character accounting and explicit repeated ranges.
- A reversible, reviewed symbol-to-legend bridge adding only references to
  existing citations; supplied semantic mappings remain unaccepted judgments.
- The frozen hotel-facts schema and instructions; Precision v2.1 and citations
  must remain enabled in any extraction experiment.
- [Results, including negative outcomes](docs/results.md),
  [doc-router source analysis](docs/doc-router-analysis.md),
  [reproduction boundaries](docs/reproduction.md), and a public [journal](JOURNAL.md).

## Run offline

Python 3.10+; the included tests need only the standard library:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 examples/synthetic_rehearsal.py
```

These commands use fabricated inputs and stubbed transports. They do not read
PDFs, access Databricks, or call Jev. The actual document experiments were
performed only in the approved Databricks workspace, not on the local machine
or GitHub Actions. Calling the transport functions directly would make a live
request and requires separate credentials and data-boundary approval.

## Findings at a glance

| Strategy | Observed result | Important limit |
|---|---|---|
| Reuse native TextPages | 0.316798 s saved out of 2.647231 s; 0.803929 s out of 2.892520 s | Two alternative native-only workloads across 236 pages, not pipeline savings |
| Compact Jev metadata requests | 32.48% fewer input tokens; $0.005799402 → $0.003915828 | 26/236 recommendations changed; not equivalent-policy evidence |
| Four concurrent Jev requests | Median router wall time 15.674 → 4.366 s (72.14% lower), four paired trials | Same input-token cost; recommendation variability persists; not end-to-end savings |
| Smaller extraction groups | Four room records recovered; class-name context recovered | Still missing dedicated class records; extraction 19.826 → 42.791 s |
| Bounded Jev verifier | 3/5 error signals flagged; 0/3 false alarms | Four correlated, previously inspected cases; not calibrated acceptance |
| Selective-parse rehearsal | 50 cases / 36 unique bundles; all 236 pages retained | Saved full-parser outputs; no new parsing or proved work avoided |
| Reversible table compaction | Complete serialized envelopes 680,282 → 654,812 bytes (3.74% smaller) | Exact parser-output preservation, not measured inference savings |
| Synthetic compact-input probe | After checker review, compact STRING passes 10/10 narrow item checks | Post-hoc diagnostic; real source quality is separate |
| Full-evidence menu compaction | 4.91% fewer input bytes; 112.352 → 117.254 s | One structured supplement price omitted; neither arm accepted |
| Source-bound price recovery | One shadow addition; compact amount coverage 55/56 → 56/56; no new inference | About 13 ms recovery kernel, 46.124 s enclosing job; incomplete quality review, no demonstrated savings |
| Schema-wide quality audit | All 33 schema paths inventoried; 43 unsupported basis defaults remain in compact and shadow outputs | Additional diagnostic work, not repair, semantic acceptance, or savings |
| Reviewed field projection | 49 supplied corrections across two shadows; about 17 ms execution per arm | Post-hoc assistant selections; 33.834 s enclosing job plus unmeasured review/preparation; neither full output accepted |
| Targeted repair extraction | Enriched input recovers seven distinct legend entries; neither arm recovers conditional preparation properties | 36.356 s extraction for both inputs together, plus preparation/evaluation/review; both rejected |
| Cited field-only composition | Seven-entry legend copied into two shadows; all other response fields unchanged | 16–22 ms kernels, 25.397 s enclosing job, plus prerequisite repair/review; no new inference or accepted savings |
| Structural table-scope control | 356 tables accounted for; one candidate matches eight reviewed target links | 20 unsupported tables; 0.111 s scan kernel / 29.361 s job; no field repair, semantic acceptance, or savings |
| Conditional field projection | Two reviewed relations / four parent applications recovered without new inference | Six visual relations remain missing; 28.7 ms kernel / 32.489 s job plus prerequisites and unmeasured review; full output rejected |
| Row-level repair extraction | Five of seven targeted preparation-marker relations appear across two unpriced preparation records | Explicit parent linkage still missing; third case misses both markers and adds unsupported price bases; 44.302 s added extraction, no full-output merge |
| Conditional donor composition | Four reviewed visual relations / eight parent applications added without new inference | Two relations / four applications remain missing; 23 ms kernel / 27.553 s job plus prerequisites and unmeasured review; full output rejected |
| Adjacent evidence with SQL preparation | Both remaining preparation markers recovered in a separate record | No explicit parent applications; two unsupported price bases; 16.735 s extraction / 33.657 s summed statements, not end-to-end latency |
| Reviewed symbol-to-legend bridge | Two more relations / four parent applications added; known conditional inventory reaches 8/8 relations and 16/16 applications | 3.3 ms bridge + 22.1 ms composition inside 37.211 s job, with prior inference/review additional; full output still rejected |

Token costs use observed usage and a retained published rate. They are not
invoices or full pipeline costs. See the results document for stage boundaries,
job startup, diagnostic denominators, and quality failures.

Findings extend through E42, including the E29 checker correction, negative
real-document compaction result, bounded router scheduling improvement, and
reviewed source-bound corrections and field-only composition. The broader audit
found field and scope defects; the latest corrections do not resolve all of them
or establish payoff.
The known conditional inventory is closed, not the whole menu or ten-document
corpus. Source transcription, repeated symbols, full field/citation review,
independent holdouts, and matched accepted-output economics remain open.
The offline suite contains 470 synthetic tests; it does not reproduce private
document accuracy or historical timing measurements.

## Safety and scope

Typed output is not truth. Structural validity is not semantic correctness.
Missing evidence must remain unknown, and review is not acceptance. Never infer
allergen safety from an absent symbol or missing extraction field.

This is an allowlisted public snapshot. It excludes PDFs, rendered pages,
source excerpts, extracted records, hosted request/response logs, credentials,
workspace identifiers, source URLs, and private run receipts. The confidential
evidence remains outside this repository; the public snapshot cannot independently
reproduce the historical accuracy or timing claims. No source-bearing Jev payload
is included or authorized by publishing this code.

See [PUBLICATION.md](PUBLICATION.md) for adaptations and known prototype limits.
No open-source license has been selected; public visibility alone is not a license.
