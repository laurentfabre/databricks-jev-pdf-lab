# Public snapshot boundary

The original experiment workspace and historical artifacts are unchanged.
This independent Git repository was assembled from an explicit file allowlist;
no private Git history or original evidence directory is imported.

## Included and adapted

- Thirteen reusable Python modules and eleven synthetic test modules.
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
- GitHub Actions configuration is an inactive example under `examples/`.
  Activating it requires workflow-write permission; publication does not request
  additional token scopes or change account permissions.

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
- E29 aggregates are preliminary frozen-checker observations. Failures still
  need attribution to model behavior, representation, or checker limitations;
  they must not be presented as independently adjudicated accuracy scores.

Publication is not deployment. No inference, dataset upload, job creation, or
data-boundary change occurs when running the offline tests and example.
