# Public snapshot boundary

The original experiment workspace and historical artifacts are unchanged.
This independent Git repository was assembled from an explicit file allowlist;
no private Git history or original evidence directory is imported.

## Included and adapted

- Twenty-three reusable Python modules and twenty-one synthetic test modules.
- Frozen benchmark schema and instructions, unchanged.
- Research findings, methodology, source-code analysis, and an offline example.
- `cache_contract.py` and its tests replace the original workspace ID with
  `example-workspace`. This is a fail-closed example pin, not a production value.
- The transport docstring names an approved workspace generically. It does not
  enforce the execution location; the private remote notebook did that separately.
- The test of private credential provisioning is omitted, together with its
  provisioning helper. The included transport tests use dummy values and stubs.
- Public documentation is newly written from aggregate observations. It does not
  contain the private journal, original notebook configuration, or source data.
- The table-compaction module and its 21 synthetic tests are unchanged copies of
  the retained experiment code. No real table content or extraction result is included.
- The annotation-preserving transform and its 12 synthetic tests are unchanged
  copies. Its literal annotation delimiter is a format marker, not a source excerpt.
- `citation_span_review.py` includes the unchanged general interval and literal
  coverage functions, with their 18 synthetic tests. The experiment-specific E29
  review function and its unused import are omitted; private fixtures are not needed.
- The bounded-concurrency module and its 18 synthetic tests are unchanged copies.
  They include a historical benchmark-specific veto, not a general safety policy.
  No real requests, private page mapping, deployment notebook, or raw ledger is included.
- The source-bound recovery module and its 37 synthetic tests are unchanged
  copies. Its dependencies are already public. No source fragments, real group
  mappings, recovered records, private evaluator, or deployment notebook is included.
- The schema-field audit module and its 23 synthetic tests are unchanged copies.
  Only generic code and fabricated fixtures are included; real field inventories,
  source scopes, manual-review records, outputs, and deployment files are excluded.
- The reviewed-field projection module and its 38 synthetic tests are unchanged
  copies. Only the generic execution engine and fabricated fixtures are included;
  real selection plans, source mappings, review evidence, and shadows are excluded.
- The cited-field composition module and its 39 synthetic tests are unchanged
  copies. Only generic code and fabricated fixtures are included. E35 is reported
  as aggregate findings; its source-specific experiment harness is not included.
  Real donor/base inputs, composition plans, origin maps, audits, and outputs
  remain private, as do all preparation/extraction/evaluation notebooks.
- GitHub Actions configuration is an inactive example under `examples/`.
  Activating it requires workflow-write permission; publication does not request
  additional token scopes or change account permissions.
- The table-scope candidate module and its 32 synthetic tests are unchanged
  copies. Only generic grammar code and fabricated fixtures are included.
  Real tables, candidates, source reviews, citation probes, experiment notebooks,
  outputs, and execution receipts remain private.
- The projection-lineage wrapper and its 21 synthetic tests are unchanged
  copies. It wraps the frozen field-projection engine without changing it.
  Only generic code and fabricated fixtures are included; real conditional
  selections, review records, source spans, audits, and derived outputs are not.
- The row-repair excerpt builder and its 24 synthetic tests are unchanged copies.
  Only generic assembly code and fabricated fixtures are included; real excerpts,
  selection plans, provenance maps, responses, notebooks, SQL, and receipts are not.

## Excluded

Original PDFs, screenshots, native text/word geometry artifacts, parser/extraction
outputs, source reference labels, source URLs, raw request/response packets,
private notebook exports, CLI receipts, statement/run identifiers, infrastructure
addresses, credentials, user configuration, and third-party repository snapshots.
Third-party work is linked and attributed, not vendored.

## Known limitations

- `selective_parse.py` intentionally retains the historical doc-8/page-12
  implementation veto to reproduce that algorithm's behavior. It is a
  benchmark-specific regression guard, not a general native-page safety rule.
- Cross-page promotion uses saved full-parser evidence. It is not a free
  pre-parse selector and cannot establish that fewer pages can safely be parsed.
- `hybrid_pages.py` is an earlier text-oriented assembly experiment; it does
  not preserve figure descriptions. Do not substitute it for the newer
  selective rehearsal when evaluating visual evidence.
- The selective rehearsal retains alternative native text and geometry; it
  does not produce a validated `ai_extract` input or resolve reading order.
- Transport ledgers are single-host prototypes. They are not a distributed,
  transactional scheduler or an exactly-once billing guarantee. Protect ledger
  directories; their contents may be sensitive in a real deployment.
- Cache validation checks provenance and scope but does not perform the
  source-level semantic evaluation that sets an acceptance decision.
- Model version `jev-1.13.0` is historical. Check current API documentation
  before any new integration; do not silently change an experiment's model.
- Table compaction preserves raw inner HTML; it is not an HTML sanitizer.
  Exact reversible serialization does not prove model interpretation, supported
  custom parser-input format, fewer serving tokens, or extraction correctness.
- E29 retains both frozen and post-hoc corrected scores. Correcting interval
  coverage does not prove semantic citation support or held-out accuracy.
- E30's one real-document pair is quality-rejected. Its compact input was smaller
  but slower in this observation and omitted a structured price. No causal latency
  distribution, matched-repeat benefit, full-corpus acceptance, or bill saving follows.
- E31 improves measured router-stage wall time only. Input-token cost is unchanged,
  recommendations vary even within an arm, and no output is quality-accepted.
  The scheduler supports the registered limits of one or four concurrent requests
  and at most twelve batches; it is not an adaptive production rate limiter.
  Page mapping retains the historical doc-8/page-12 veto. Partial/unknown rounds
  require investigation, not automatic replay in a fresh directory.
- E32 supplies a deterministic candidate/control, not a Jev integration. Source
  groups and translation equivalence are caller hypotheses, its wording filter
  is incomplete, and same amount/currency does not validate a price basis.
  Its one reviewed addition is not an independently labeled holdout result,
  full-output acceptance, general false-positive estimate, or proven saving.
  Shadow additions inherit citation IDs, not model-generated confidence.
- E33 inventories fields and exact strings; it cannot establish source fidelity,
  multilingual equivalence, semantic citation support, or complete fact coverage.
  Its schema walker supports the included extraction-schema shape, not arbitrary
  JSON Schema. Caller-provided source scopes require independent validation.
  Audit results contain copied field values and must remain inside the approved
  data boundary when real inputs are used. Empty allergen arrays prove no safety
  property. All semantic statuses remain unevaluated and acceptance stays false.
  The separate assistant source review is post-hoc, not independent labeling.
- E34 executes supplied post-hoc assistant selections; it does not discover or
  semantically validate corrections. Review hashes bind supplied records, not
  their truth or reviewer identity. The engine accepts the benchmark's schema
  shape and span-cited Precision responses, not arbitrary schemas or image-only
  evidence. Existing citation coverage proves literal presence, not correct scope.
  Explicit null selections are reviewed absence judgments, not a general rule
  that missing literals imply unstated facts. Original metadata is preserved;
  it must not be represented as new service-generated confidence for the edits.
  Real plans and audits contain source/output values and must remain private.
  All shadows remain unaccepted; selection, review, and preparation costs are
  outside the measured projection kernels.
- E35 adds post-hoc assistant image observations, not independent source labels.
  Its legend improvement does not repair conditional scope or accept the output.
  Corrected matcher false negatives do not excuse omitted multilingual wording.
- E36 accepts only reviewed root-field selections under the benchmark's schema
  shape and Precision v2.1 span-citation envelope, not arbitrary JSON Schema.
  Review and origin hashes bind caller-supplied records; they do not validate
  reviewer identity, source truth, origin-map completeness, or citation semantics.
  Rebased citations preserve existing spans; they are not newly generated service
  evidence. Inherited metadata must not be presented as confidence in composed
  fields. Results are explicitly derived and unaccepted. Real composite text and
  audits contain private data. Prerequisite extraction and review are not free.

Publication is not deployment. No inference, dataset upload, job creation, or
data-boundary change occurs when running the offline tests and example.

The E37 scope scanner supports a narrow rectangular HTML grammar with paired
name/euro-price columns. It cannot interpret headings, negation, symbol meanings,
or semantic ownership. Even nonconditional and negated headings can produce a
candidate; tests deliberately expose this limit. Unsupported inputs abstain,
and no candidate never proves absence of conditional facts. The single known
target comparison is post-hoc development review, not an independent holdout.
Returned spans contain source text and must remain private for real inputs.

The E38 lineage wrapper verifies identity and exact restoration, not semantic
ownership, reviewer identity, or citation truth. It preserves the previous
derivation beneath a new, explicitly non-service label. Inherited metadata is
not new service confidence, and all acceptance flags remain false. Supplied
conditional selections are post-hoc assistant judgments, not an automated
selector. The two recovered relations do not establish generalization or full
output acceptance. Real parent lineage and audit records must remain private.

The E39 excerpt builder checks exact copying, supplied bindings, a narrow HTML
grammar, and segment accounting. It does not authenticate the supplied review,
prove correct ownership, discover which rows to select, or validate that all
necessary context is present. It expects two-parent development cases with a
separate legend page; it is not a general document slicer. Outputs explicitly
remain partial and unaccepted, and omitted material stays required. Real output
strings, plans, and origin maps contain private content. Five observed marker
relations in separate preparation records are not five completed parent-scoped
repairs. The latest full-menu output is unchanged and rejected.
