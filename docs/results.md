# Results: least to most complex

Status: 2026-09-19. Ten documents / 236 physical pages. Frozen hotel-facts
schema, original exact values, Precision v2.1, and citations are invariant.
**No incremental Jev benefit at equal accepted output quality has been shown.**

## Ordered comparisons

| Level | Strategy | Observed result | Interpretation |
|---|---|---|---|
| 0 | Managed parse + extraction, all pages | Historical ten-document totals 513.742 / 471.350 s | Outputs incomplete; not an accepted quality baseline |
| 1 | Fixed native eligibility rule | 194 native-layout / 42 managed recommendations | Zero model calls; recommendation counts are not work saved |
| 2 | Document Jev with an empty-text guard | 217 native / 12 managed / 7 review; 1.536377 s HTTP | No demonstrated improvement over the deterministic control |
| 3 | Page Jev | 197 native / 39 review; 11.047906 s HTTP | More router work; quality and review cost unresolved |
| 4 | Finer extraction groups with the same no-Jev control | Four missing room records recovered; class-name context recovered | Still zero dedicated records for twelve classes; not Jev-attributable |
| 5 | Source-grounded Jev verifier | Three of five positive error labels flagged, zero of three false alarms | Misses two error signals; no accepted fallback or savings |
| 6 | Selective parse + complete reassembly rehearsal | 50 cases / 36 distinct bundles | Page integrity demonstrated, not semantic completeness or live parser savings |

The simple rule requires at least 200 native characters and no replacement
characters. It is a development comparator, not a validated quality policy.
The document guard only excludes known absent text; it is not that same rule.
Level 4 selected the same work with or without Jev, so its recovery belongs to
chunking. Previously inspected documents are development data, not untouched
holdouts. Retained inference was shared where work was identical.

## How much total did the small native optimization save?

Across the same ten documents, repeated native TextPage reuse preserved exact
view hashes, strings, ordering, and coordinates:

| Alternative native workload | Baseline sum of document medians | Saved | Scope |
|---|---:|---:|---|
| Text + words | 2.647231 s | 0.316798 s | Native kernel only |
| Four routing views | 2.892520 s | 0.803929 s | Native kernel only |

These are alternative workloads, not additive savings. They are not measured
improvements against the 471–514-second managed parse/extraction totals.
The native optimization generalizes across this corpus; that is not evidence
of generalization to unseen layouts or of a faster accepted extraction pipeline.

## Compact metadata requests (E24)

Twelve requests / 236 page questions, retaining shared policy and method definitions:

| Metric | Original | Compact |
|---|---:|---:|
| Input tokens | 138,081 | 93,234 |
| Output tokens | 12,292 | 12,298 |
| Published-rate token cost | $0.005799402 | $0.003915828 |
| Aggregate HTTP time | 11.047906 s | 9.256936 s |

Input-token cost fell 32.4788%. HTTP was 1.790971 s lower out of 11.047906 s,
but this is an historical/current single-trial comparison, not matched repeats.
Only 210/236 routes agreed: 26 changed, including four review-to-native changes.
There were two response-contract exceptions in each arm. The compact experiment
took 21.065771 s; its enclosing job took 48.491 s (5 s reported setup, 42 s
reported execution). None of those figures proves an equivalent policy or
accepted full-pipeline saving.

## Chunking (E20 → E22)

One previously inspected 11-page document changed from one extraction input to
six consecutive groups. All pages remained present, while repeated context
increased total characters from 9,017 to 9,937. Statement time rose from
19.826 to 42.791 s; execution components were 18.595 and 36.506 s. These are
not matched cache conditions, per-chunk timings, or full-pipeline costs.

Four room records and twelve class names in club details were recovered.
Neither version produced the twelve required dedicated class records.
The grouped result also retained near-duplicate facilities and naming
inconsistency. Both outputs remain rejected for complete benchmark quality.

## Bounded verifier (E23)

Four uniquely authorized packets, two source sections paired with two saved
extractions: eight independent-question signals, but correlated examples.
No PDFs or images were sent. The predeclared threshold was P(error) ≥ 0.7;
below threshold means unresolved, never accepted.

| Case | P(missing dedicated record) | P(missing contextual mention) | Error labels |
|---|---:|---:|---|
| Room section / whole extraction | 0.91 | 0.84 | true / true |
| Room section / grouped extraction | 0.18 | 0.27 | false / false |
| Class section / whole extraction | 0.71 | 0.66 | true / true |
| Class section / grouped extraction | 0.43 | 0.32 | true / false |

Three true positives, three true negatives, two missed error signals, no false
alarms. The existing deterministic inventory control catches dedicated-record
omissions, including the one Jev misses. Lowering a threshold after observing
these labels is fitting this sample, not calibration or generalization.

Usage: 6,312 input / 176 output tokens; $0.000265104 published-rate token cost.
Timing: 3.257748 s HTTP, 6.261867 s transport plus durable ledger writes,
7.998106 s experiment, 31.769 s enclosing job. Four calls exactly once,
zero retries or fallback extractions. This added verification work did not
avoid extraction. The bounded permission was consumed and does not extend
to new source-bearing requests.

## Full-corpus selective rehearsal (E25)

All five arms reuse saved native artifacts and the already-paid E0 parser.
Review recommendations use a managed rehearsal leg but remain unresolved.
A known failing whole-page native implementation is vetoed once per candidate
arm. No PDFs were read and no model or parser was called.

| Arm | Effective native / managed pages | Native pages with numeric lexical differences vs E0 | Native pages whose E0 result has figure descriptions | Unresolved original review |
|---|---:|---:|---:|---:|
| Managed all | 0 / 236 | 0 | 0 | 0 |
| Fixed rule | 193 / 43 | 44 / 193 | 168 / 193 | 0 |
| Document Jev | 216 / 20 | 56 / 216 | 190 / 216 | 7 |
| Page Jev | 196 / 40 | 51 / 196 | 172 / 196 | 39 |
| Compact page Jev | 196 / 40 | 50 / 196 | 173 / 196 | 33 |

Managed word tokens absent from native text occurred on 170, 189, 172, and
173 effective native pages respectively. Table elements appeared on 75, 75,
74, and 74. These overlapping diagnostics are neither counts of required-fact
omissions nor proof the other pages are safe. E0 itself is imperfect;
generated descriptions can be wrong. Exact tokens can still have wrong row
or column associations.

Sixteen remote synthetic tests passed. All 50 cases retain complete physical
page inventories and unchanged selected managed elements; 36 bundles are
distinct. No cross-page promotion or unlocated element occurred in this corpus.
Synthetic tests cover both cases. Cross-page closure would require full-parser
evidence and is a profiling constraint, not a free deployable routing rule.

Timing: 8.517998 s saved-parser fetch, 8.634450 s assembly/comparison/writes,
19.381964 s total experiment, 39.741 s enclosing job (5 s reported setup,
34 s reported execution). These are rehearsal overheads, not savings.

## Selected-page parser probe (E26)

Three original-document inputs requested five selected pages; all requested
original page IDs and bbox page assignments were retained. Reassembly preserved
all 30 physical pages across those documents. Only two of five selected-page
evidence projections exactly matched the saved full-parser output.

The frozen marker check scored 40/41. Subsequent source review found the failed
reference label was wrong, not the parsed value; the correction is recorded
separately without changing the historical score. Review also found a visual
detail omitted from a generated description. None of the bundles is accepted
for complete downstream extraction quality.

Statement time was 407.769 s: 384.845 s from queue start to compilation,
2.457 s compilation, and 20.340 s execution. Shared-warehouse contention
dominates that observation; it is neither isolated parser latency nor speedup
evidence. Evaluation added 10.380658 s within a 47.745 s job. No matched
baseline or safe-to-skip policy was established.

## Corrected lexical diagnostics (E27)

Removing HTML wrappers from a separate diagnostic reduced discrepancy counts
on the same eligible pages. No extraction output was changed.

| Arm | Eligible native pages | Raw → visible word-token discrepancies |
|---|---:|---:|
| Fixed rule | 190 | 19,488 → 1,972 |
| Document Jev | 213 | 19,678 → 2,162 |
| Page Jev | 193 | 19,387 → 1,913 |
| Compact Jev | 193 | 19,308 → 1,942 |

Three unsupported projections remain unknown, not zero-discrepancy successes.
These are measurement corrections, not accuracy improvements, missing-fact
counts, or evidence that native pages are safe. The saved-artifact experiment
took 4.259082 s; its enclosing job took 35.122 s. No PDF or AI calls occurred.

## Reversible table serialization (E28)

Across ten documents / 236 pages, all parser envelopes restored exactly.
Of 356 table elements, 241 became smaller and 115 stayed original because
compaction was not smaller. None was unsupported in this corpus. Unsupported
structures fall back to unchanged content in the reusable codec.

| Measurement | Original | Candidate | Reduction |
|---|---:|---:|---:|
| Content characters | 293,381 | 252,677 | 13.8741% |
| Complete compact-JSON envelope bytes | 680,282 | 654,812 | 3.7440% |

JSON escaping and unchanged metadata substantially reduce the apparent gain.
Codec work took 0.181395 s, the experiment 4.383047 s, and its job 26.110 s.
All 21 remote codec tests passed. The same unchanged module and synthetic tests
are included in this repository.

This preserves an imperfect parser output, not source truth. There is no
measured serving-token, invoice, model-latency, or incremental Jev benefit.
The deterministic transform is equally available to the no-Jev control.
Byte reduction alone does not justify a full-corpus inference trial.

## Synthetic compact-input probe (E29; preliminary)

Four synthetic inputs compared HTML/compact representations and STRING/VARIANT
input types, using the frozen full schema, Precision v2.1, and citations.
Each contained the same ten offerings on three synthetic pages. These were
four logical extraction inputs in two concurrent, two-row SQL statements,
run in the approved Databricks workspace. No PDF, real source data, parser,
or Jev request was involved.

All four returned the exact ten-name inventory, no service error, and the
expected citation kind. The frozen narrow checker produced:

| Input | Citation kind / count | Items passing all narrow checks |
|---|---|---:|
| STRING compact | span / 10 | 7/10 |
| STRING HTML | span / 10 | 2/10 |
| VARIANT compact | bbox / 4 | 0/10 |
| VARIANT HTML | bbox / 4 | 0/10 |

**No case passes the whole narrow gate. These are not adjudicated accuracy
scores.** Both original controls also fail, so the counts do not establish
that compaction caused failures or improved quality. Model behavior,
representation differences, and checker limitations still need separate
review. Policies, legends, price basis, and details are not fully checked;
citation overlap alone does not prove evidence supports a claim.

The VARIANT statement took 31.327 s total and the STRING statement 31.408 s.
Each mixes original and compact inputs; these are not original-versus-compact
latency measurements. The saved-output evaluation took 10.619316 s including
9.210875 s fetch, within a 35.549 s job (5 s reported setup, 29 s execution).
All 12 remote evaluator tests passed. Artifact/hash checks confirm consistency,
not semantic correctness. No inference was repeated for
this publication. The next gate is review of the retained failures, not a new
full-corpus run or deployment of the compact representation.

## What would establish payoff?

Freeze a candidate and a no-Jev ablation before an independently labeled,
unseen-layout evaluation. Validate selective parser page IDs and complete
reassembly. Evaluate every required record, exact value, visual association,
and citation under the unchanged contract. Include preparation, router,
parser, extractor, fallback, review, startup, and attributable compute costs.
Separate cold/new-document latency from warm reuse and throughput. Repeat
matched trials and report cost per accepted document—not router price alone.

Historical raw data and execution receipts remain private. The public tests
exercise the code with synthetic fixtures; they cannot substantiate the
historical source-level accuracy claims independently.
