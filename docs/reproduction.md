# Reproduction and execution boundaries

## Offline checks

From the repository root, Python 3.10+:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 examples/synthetic_rehearsal.py
python3 scripts/check_publication.py
```

There are 93 included synthetic tests. The original private project had 248
passing synthetic tests at publication, including source-specific evaluators
not copied here. The public number must not be presented as 248.

The example fabricates a three-page document in memory. Tests stub the hosted
transport and PyMuPDF page objects. No PDF library, model credential, or
Databricks connection is needed. These tests validate implementation behavior,
not historical timing, billing, or semantic accuracy on actual source files.

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
  [extraction cascades](https://docs.typesafe.ai/cookbooks/sde_cascade).
- [Databricks ai_parse_document](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document)
  and [ai_extract](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_extract).

TypeSafe's skill guidance informed narrow judgments, deterministic checks, and
explicit uncertainty. Databricks skill guidance informed persisted stages and
page selection. Neither proves truth, authorizes data transfer, or demonstrates
an end-to-end gain.
