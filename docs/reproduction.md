# Reproduction and execution boundaries

## Offline checks

From the repository root, Python 3.10+:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 examples/synthetic_rehearsal.py
python3 scripts/check_publication.py
```

There are 260 included synthetic tests: 93 from the initial snapshot, 21
table-codec tests, 18 citation-interval tests, and 12 annotation-preservation
tests, plus 18 bounded-concurrency, 37 source-bound-recovery, and 23 schema-field
audit tests, plus 38 reviewed-field-projection tests. The private project recorded 450
passing synthetic tests, including evaluators not copied here. The public
number must not be presented as 450.

The example fabricates a three-page document in memory. Tests stub the hosted
transport and PyMuPDF page objects. No PDF library, model credential, or
Databricks connection is needed. These tests validate implementation behavior,
not historical timing, billing, or semantic accuracy on actual source files.

The codec tests use fabricated HTML strings and parser-shaped dictionaries.
They check exact restoration, unchanged metadata, and fallback for unsupported
or larger representations. They do not call an extractor, authorize real-data
processing locally, or prove that a model will interpret the compact input.

Citation tests cover adjacent and overlapping intervals, uncited gaps, invalid
IDs/bounds, Unicode character offsets, and source-scope restrictions. Their
`supported` result means exact literal coverage only, not entailment or correct
row association. Annotation tests preserve all supplied observations verbatim;
they do not validate whether those observations are true.

Concurrency tests use stubbed HTTP responses, barriers, and dummy credentials.
They check the in-flight bound, stop-and-drain behavior, replay prevention,
wire-payload identity, and question-to-page binding despite sorted JSON keys.
They do not reproduce hosted latency or establish stable semantic decisions.
Calling `run_round` without a stub sender makes live requests; that requires
separate credentials and data-boundary approval in the approved workspace.
Retain interrupted-round directories for investigation; do not bypass markers
by creating another directory and resubmitting an unknown outcome.

Recovery tests use fabricated cited phrases, response fields, and source groups.
They cover exact money parsing, identity anchors, page/ownership ambiguity,
citation gaps, unsupported syntax, immutable original fields, and idempotency.
They do not validate real source grouping, translation equivalence, or semantic
support. Every proposed shadow edit remains review-required and not accepted.
No hosted call or document read occurs inside `source_bound_recovery.derive`.

Field-audit tests use fabricated schema nodes, text, citation spans, and responses.
They cover schema-path accounting, missing/null/empty values, source-scope and
hash guards, immutable inputs, type mismatches, citation gaps, wrapper handling,
and Precision v2.1 response checks. Every semantic status stays unevaluated;
no row is accepted. Literal matches do not establish correct meaning or source
fidelity, and literal misses may reflect bilingual formatting rather than error.
`schema_field_audit.audit` performs no I/O, but its returned inventory copies
field values; do not publish real-data inventories. The public tests do not
reproduce the private E33 manual source review or its historical measurements.

Projection tests use fabricated review plans, source spans, and responses. They
cover stale input/schema/scope bindings, exact field copying, source-page guards,
citation gaps, overlapping operations, explicit reviewed nulls, immutable raw
outputs/metadata, replay rejection, and exact reversal. They do not validate
the supplied semantic selections. The review digest is an integrity binding,
not authentication or proof of truth. `reviewed_field_projection.project` has
no I/O or model call; real plans and returned audits still contain private data.
No real E34 selection plan or source review is included in this repository.

`examples/github-actions-offline-tests.yml` is an inactive CI template. No
workflow is installed by this snapshot. An authorized maintainer may install
it separately; its commands run only these offline synthetic checks.

## Run your own controlled Databricks study

The private deployment notebooks and original inputs are deliberately absent.
This is not a one-command reproduction of the historical experiments.

1. Obtain permission for the documents, compute workspace, and every inference
   destination. Select an explicit CLI profile; never use an implicit default.
2. Preserve original bytes and hashes in an approved Unity Catalog Volume.
   Hash parser recipes, the schema, instructions, metadata options, model
   versions, and exact source-page scope.
3. Materialize each parsing/extraction stage exactly once. Keep statement/run
   handles and raw outputs privately; resume observations rather than retry
   an inference whose outcome is unknown.
4. Run document processing and experiments only in the approved workspace.
   Derive native text and geometry there. Diagnostics never authorize external
   source-text egress. The metadata router rejects arbitrary text and URLs.
5. Treat selected-page parsing as a new candidate, not an established win.
   Databricks `pageRange` is 1-indexed; confirm returned page identities and
   preserve cross-page context. The E25 rehearsal requires already-paid full
   parsing and therefore cannot be its own cheap selector.
6. Use `ai_extract` with the frozen schema, instructions, version `2.1`, mode
   `precision`, and citations enabled. Record effective options in outputs;
   do not fall back to a different mode to improve a timing result.
7. Separate structural checks from a source-backed inventory of all required
   facts, exact values, relationships, dietary symbols, and page citations.
8. Freeze a candidate and evaluate independent unseen layouts. Compare with a
   no-Jev ablation, include review/fallback and startup, and report matched
   repeat distributions and cost per accepted output.

Before a new integration, check current primary documentation:

- [TypeSafe documentation index](https://docs.typesafe.ai/llms.txt),
  [routing](https://docs.typesafe.ai/patterns/intent-routing), and
  [extraction cascades](https://docs.typesafe.ai/cookbooks/sde_cascade), plus
  [citation checks](https://docs.typesafe.ai/cookbooks/citation_check).
- [Databricks ai_parse_document](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document)
  and [ai_extract](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_extract).

TypeSafe's skill guidance informed narrow judgments, deterministic checks, and
explicit uncertainty. Databricks skill guidance informed persisted stages and
page selection. Neither proves truth, authorizes data transfer, or demonstrates
an end-to-end gain.
