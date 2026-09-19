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

## Synthetic compact-input probe (E29; frozen results and later review)

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

**No case passes the original whole narrow gate.** These frozen scores remain
unchanged. Subsequent saved-output review separated checker defects from real
output failures; it does not turn these results into held-out accuracy scores.

The VARIANT statement took 31.327 s total and the STRING statement 31.408 s.
Each mixes original and compact inputs; these are not original-versus-compact
latency measurements. The saved-output evaluation took 10.619316 s including
9.210875 s fetch, within a 35.549 s job (5 s reported setup, 29 s execution).
All 12 remote evaluator tests passed. Artifact/hash checks confirm consistency,
not semantic correctness. No inference was repeated for this publication.

### Citation-checker correction (S035)

The original checker required each complete name inside a single cited span.
Seven name flags across the two STRING outputs were false: adjacent cited
spans jointly covered the literal. The separate checker merges overlapping or
adjacent intervals only; it never bridges an uncited gap or repairs a response.

| Input | Frozen narrow items | Reviewed narrow items | Remaining failure |
|---|---:|---:|---|
| STRING compact | 7/10 | 10/10 | None in this bounded fixture |
| STRING HTML | 2/10 | 3/10 | Six unsupported amount citations, two unsupported name citations, omitted policy |
| VARIANT compact | 0/10 | 0/10 | Empty source-page fields despite bbox location |
| VARIANT HTML | 0/10 | 0/10 | Same raw page-field failure |

Compact STRING also passes separately added value/policy checks. Manual review
covered all ten synthetic rows, sizes, bases, marker/allergen associations,
pages, and both global policies. A small table remained HTML because compact
encoding was larger; this is not a universal JSON-only input contract.

The omitted HTML policy distinguishes unstated allergens from allergen-free
food. It is a genuine omission, not a citation-checker defect. Citation bounds
and exact literal matches alone still cannot establish semantic correctness.
No output was changed and no source-page field was filled automatically.

This saved-output review took 1.875500 s within a 21.466 s job; 18 remote
synthetic tests passed, with no new AI call or PDF read. It justified a bounded
real-evidence quality screen, not an accepted optimization or Jev benefit.

## Full-evidence menu pair (E30)

One previously inspected seven-page menu, 49 source elements, all original
page labels, and the entire 12,578-character symbol-annotation suffix. The
original arm exactly reused the prior enriched input. Eight table wrappers
were compacted in the candidate; the complete original restores exactly.
No evidence was selected away. Both new one-row statements used the same
frozen schema/instructions, Precision v2.1, and citations.

| Metric | Original | Compact |
|---|---:|---:|
| Complete input bytes | 27,183 | 25,849 |
| Input characters | 24,936 | 23,602 |
| Final statement total | 112.352 s | 117.254 s |
| Execution component | 110.996 s | 115.908 s |
| Matched offerings / reference | 52/52 | 52/52 |
| Structured price amounts / reference | 56/56 | 55/56 |
| Marker associations / reference | 48/49 | 48/49 |
| Exact physical-page records | 52/52 | 52/52 |

**4.9075% fewer bytes, but 4.902 s slower in this single concurrent pair.**
Neither used a query-result cache. This is not a repeated latency distribution,
an isolated model-service time, or a proven causal slowdown. No serving-token
or attributable billing reduction was measured.

Inspection confirmed that the compact output retained a supplement in prose
but omitted its dedicated structured price; a mention is not field completeness.
Both outputs also omit one explicit dietary attribute from its required marker
field. Neither is accepted. Recognized legend categories differ between arms,
and complete preparation-scope, multilingual-detail, policy, allergen, price-basis,
and semantic citation review remains unfinished. The reference is partial,
previously inspected, and not independently double-labelled.

All 412 original and 457 compact non-null fields pass citation ID/bounds checks;
that does not prove their citations support the fields. The original source
observations and extraction outputs remain unchanged and private.

Codec work: 0.005745 s. Preparation: 14.076467 s, including 12.794898 s Delta
write/verification, within a 130.844 s job (96 s setup, 34 s execution).
Saved-output evaluation: 12.366970 s within a 40.742 s job (5 s setup, 35 s
execution; task elapsed 40.265 s); 29 remote tests passed. Twelve preparation tests also passed.
These are research overheads, not savings. No fallback, parser, or Jev call
was added. The deterministic transform is equally available without Jev.

Decision: do not promote this candidate or launch a full-corpus compaction
rollout on these results. Equal-quality end-to-end savings and incremental
Jev payoff remain unproven; byte conservation is useful engineering evidence,
not extraction-quality acceptance.

## Bounded Jev concurrency (E31)

The same twelve compact metadata-only requests cover all 236 pages per pass.
Model `jev-1.13.0`, wire payloads, questions, transport, and strict response policy
are unchanged. Only client scheduling changes: one versus four requests in flight.
This is separate from evaluating many questions within each shared-state request.

Four pairs used balanced arm order: serial/parallel, parallel/serial,
parallel/serial, serial/parallel. Both arms in each pair used the same batch
order, rotated by 0, 3, 6, or 9 positions. No warmup was discarded. There were
96 registered requests and 1,979,808 metadata wire bytes, with no retries,
source-bearing payloads, PDF reads, parser/extractor calls, or route acceptance.

| Metric | Serial | Four concurrent |
|---|---:|---:|
| Median router wall time | 15.674136342 s | 4.366265361 s |
| Range across four rounds | 15.389191–15.983365 s | 4.209667–4.482054 s |
| Input tokens per pass | 93,234 | 93,234 |
| Published-rate input cost per pass | $0.003915828 | $0.003915828 |
| Response-contract exceptions per pass | 3–5 | 3–6 |

**72.1435% lower median router wall time; 3.5898× ratio of medians.**
All four pairs saved time: 11.135898–11.501311 s per pass. The timer includes
scheduling, per-request validation, HTTP/TLS, and durable request/response/result
writes. It excludes initial preflight, round summary writes, tests, final study
analysis, and Jobs startup. Experiment time was 85.560078 s; enclosing job
115.170 s, task 114.736 s (5 s reported setup / 109 s execution).
Do not subtract these router-stage savings from a historical pipeline total.

Identical prompts did not produce identical recommendations. Paired guarded
candidate agreement was 221, 221, 222, and 223 of 236; raw service-choice
agreement was 228–230/236. Within serial rounds, guarded agreement was
219–223/236; within parallel rounds, 222–227/236. Variation cannot all be
attributed to concurrency. Contract exceptions remain review-only; the known
native-implementation veto remains. No semantic-equivalence claim follows.

The no-Jev rule still recommends 194 native-layout / 42 managed pages with
zero model calls. Its 0.000269272 s kernel excludes diagnostics and is not
quality-accepted. Neither that timing nor E31 establishes safe work avoided.

The new scheduler binds explicit question IDs to physical pages, never JSON
object order or completion order (`route_10` can precede `route_2`). Durable
round markers prohibit automatic replay of completed or interrupted work;
on failure, it stops scheduling after observation and drains in-flight calls.
All 18 new synthetic tests pass. Private integrity checks verified all 96
ledgers, payload/response hashes, usage, bindings, and measured HTTP intervals.
These checks establish accounting consistency, not source-level correctness.

Decision: retain this measured router-overhead improvement. No input-token
saving, attributable compute-cost saving, accepted end-to-end benefit, or
incremental semantic Jev payoff has been established. Four paired trials on
one workload do not demonstrate performance across other services or loads.

## Source-bound structured-price recovery (E32)

Both saved E30 responses were scanned without reading PDFs or repeating
parsing, extraction, or Jev inference. This deterministic control looks for a
narrow parenthesized plus-price grammar already retained in an output's name
or details and fully covered by source-span citations. It requires a cited
name anchor, unique source-group/output ownership, and the same physical page.
Unknown money syntax, ambiguous ownership, missing citations, and recognized
negative or conditional wording abstain. It never overwrites existing fields.

| Metric | Original arm | Compact arm |
|---|---:|---:|
| Items scanned | 52 | 52 |
| Candidate occurrences | 0 | 2 |
| Shadow structured-price additions | 0 | 1 |
| Structured amount coverage, before → after | 56/56 → 56/56 | 55/56 → 56/56 |
| Marker associations, unchanged | 48/49 | 48/49 |
| Offerings / physical-page records, unchanged | 52/52 | 52/52 |
| Recovery kernel | 0.013418645 s | 0.012942240 s |

The two compact candidates are language alternatives for one supplement, not
two additional prices. Their full literal conditions remain in the private
audit; the selected complete phrase becomes the shadow price basis. Existing
fields and raw outputs remain unchanged. New fields inherit citation IDs,
not invented model confidence or new service citations.

Assistant visual review of the retained source page supports this one delta.
It is neither independent human labeling nor held-out evaluation. Source
grouping and translation equivalence remain caller hypotheses, literal coverage
does not prove meaning, and the wording filter is incomplete. An existing
amount/currency pair suppresses an addition without certifying its basis.
The unchanged original arm is not a general false-positive-rate measurement.

All 37 new synthetic tests passed locally and remotely. The experiment including
tests, reads, and writes took 2.920191396 s; the enclosing job took 46.124 s
(task 45.668 s; reported setup 5 s / execution 40 s). These are additional costs,
not measured savings. In particular, no evidence establishes that E30's
117.254-second extraction needed to be repeated or was avoided.

Decision: retain the narrow recovery and immutable shadow/audit pattern. Neither
full output is accepted: dietary/preparation scope, other required fields,
and semantic citations remain unfinished. E30's raw result is unchanged.
No incremental Jev benefit, full-corpus generalization, matched end-to-end
latency saving, or attributable billing reduction is established.

## Schema-wide field audit and source review (E33)

E33 inventoried three retained outputs: E30 original, E30 compact, and E32's
compact shadow. It accounts for every path in the unchanged schema, concrete
fields and containers, missing/null/empty values, unexpected fields, and
whole-string citation coverage restricted to original-source scopes. It does
not repair outputs or evaluate semantics. No PDF read, parsing, extraction,
Jev call, or SQL write occurred in the deterministic experiment.

| Metric | Original | Compact | Compact shadow |
|---|---:|---:|---:|
| Items | 52 | 52 | 52 |
| Schema paths inventoried | 33 | 33 | 33 |
| Concrete field/container slots | 831 | 837 | 841 |
| Price-basis slots | 56 | 55 | 56 |
| Nonempty string bases | 14 | 55 | 56 |
| Whole basis literal absent from source scopes | 14 | 43 | 43 |
| Cited whole-literal bases | 0 | 11 | 12 |
| Unsupported generic basis defaults, source-reviewed | 0 | 43 | 43 |
| Empty allergen arrays | 52 | 52 | 52 |
| Audit kernel | 0.031780935 s | 0.036158824 s | 0.034356387 s |

Slots include containers and repeated fields, not independently verified facts.
The sole schema path with no concrete slot is the element of the empty allergen
arrays. That is unknown source presence, not evidence that allergens are absent.
Every automated semantic status remains unevaluated and every accepted flag false.

Do not treat literal mismatches as semantic errors. All fourteen original
nonempty bases join bilingual phrases and therefore fail whole-string matching.
One compact basis also has a cited equivalent in the other source language;
the unmatched English literal alone does not establish a citation defect.
By contrast, the 43 generic defaults are unsupported in source review and violate
the frozen verbatim-basis/null-if-unstated requirement. E32 leaves them unchanged.

A separate post-hoc assistant review inspected all seven retained source-page
renders and all 52 item field sets in both E30 arms, plus document, policy,
and legend fields. It covered nineteen leaf-field categories and recorded twelve
scoped findings. This was not independent labeling, complete multilingual
validation, or full semantic citation acceptance. Findings include:

- Missing or conflated dietary legend distinctions and preparation-specific
  properties lost from their conditional scope.
- An explicit dietary property retained in prose but missing from its dedicated
  field, and a document policy absent from the original arm.
- Parser-origin characters propagated into names, distinct from a compact-only
  extraction transcription error.
- A qualifier lost when retaining only one language, and repeated symbols reduced
  to a generic label. Symbol counts are not calibrated intensity levels.
- Unresolved allergen evidence. Empty arrays do not authorize safety claims.

These findings are summarized without publishing source text, item-level outputs,
source mappings, or the private review evidence. They establish reasons to reject
the inspected outputs, not a measured general accuracy or false-positive rate.

All 23 new synthetic tests passed locally and remotely. The experiment including
tests, reads, and writes took 2.198846904 s; the enclosing job took 26.563 s
(task 26.123 s; reported setup 5 s / execution 21 s). These are additional
diagnostic costs, not savings. No historical inference was repeated.

Decision: do not promote compact output because one price was recovered.
Separate source/parser defects, exact field assembly, semantic scope decisions,
and full-output acceptance. The reusable audit improves visibility into failures;
it does not prove a Jev advantage, generalization, or end-to-end cost reduction.

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
