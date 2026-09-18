# What transfers from doc-router?

Source review only, pinned to
[`misbahsy/doc-router@8977d2ba1fd672fbbc85f01e630a2d5de6a406aa`](https://github.com/misbahsy/doc-router/tree/8977d2ba1fd672fbbc85f01e630a2d5de6a406aa).
No repository build, OCR-provider call, or independent benchmark reproduction.

## The valuable idea

Avoid unnecessary expensive parsing while retaining every page for extraction.
Use Jev for uncertainty ordinary code cannot resolve—not to rediscover whether
a native text layer exists. Databricks can implement selected-page parsing with
`ai_parse_document(..., map('pageRange', ...))`; adopting another OCR host or
the repository's Rust implementation is unnecessary.

## Reported payoff and its limits

The [guide](https://github.com/misbahsy/doc-router/blob/8977d2ba1fd672fbbc85f01e630a2d5de6a406aa/docs/GUIDE.md)
reports 19 documents / 155 pages:

| Measure | OCR all | Jev routed |
|---|---:|---:|
| OCR pages / requests | 155 / 19 | 87 / 13 |
| OCR-stage time | 35.578 s | 20.666 s |
| Time including classifier | 35.578 s | 23.680 s |
| OCR plus stated judge cost | $0.3100 | $0.1783 |
| Needed-OCR pages skipped | 0 | 9 |

The reported end-to-end difference is 11.898 s / 33.44%, not the OCR-only
1.72× headline. But nine of 87 needed-OCR pages are missed. Equal counts of
selected and needed pages conceal nine false skips and nine unnecessary OCR
pages. This is not equal-quality evidence.

The corpus comprises ten synthetic and nine generated adversarial fixtures,
not independent customer holdouts. The checked-in
[benchmark](https://github.com/misbahsy/doc-router/blob/8977d2ba1fd672fbbc85f01e630a2d5de6a406aa/crates/doc-router-bench/src/bench.rs)
times `classify_with` and scores routing, not final OCR or complete extracted
facts. Its cost block prices pages arithmetically. Raw live-OCR timing receipts
were not found in the reviewed tree. Treat the guide's timings as
repository-reported, not reproduced here.

## Techniques, least to most complex

| Level | Technique | Databricks adaptation | Proof needed |
|---|---|---|---|
| 1 | Full-page inventory | Inspect every physical page; retain original IDs | No page lost under a document-level label |
| 2 | Reuse evidence and batch questions | Saved native views and shared policy/state | Equivalent or better decisions with less work |
| 3 | Jev only on ambiguity | Code handles definite failures; Jev judges uncertain text | Held-out benefit over identical no-Jev rules |
| 4 | Selective parse and complete reassembly | `pageRange`, strict merge, unchanged Precision extraction | All required facts, visual associations, and citations |
| 5 | Overlap independent work | Bounded native preparation alongside managed parsing | Critical-path improvement without extra calls/startup |
| 6 | Verify and selectively escalate | Exact checks, narrow omission questions, validated fallback | Lower total cost per accepted document |

The [full-page classifier](https://github.com/misbahsy/doc-router/blob/8977d2ba1fd672fbbc85f01e630a2d5de6a406aa/crates/doc-router/src/classify.rs)
is useful: sampling a few pages can overlook mixed raster/native documents.
Our rehearsal likewise retains all physical pages.

The [Jev wire format](https://github.com/misbahsy/doc-router/blob/8977d2ba1fd672fbbc85f01e630a2d5de6a406aa/crates/doc-router-jev/src/wire.rs)
includes up to 2,000 native characters per page, original length, truncation,
and inspector findings, with 50-page batches and a soft 256 KiB bound. Its
binary question asks whether OCR would recover missing text. This is more
grounded than our metadata-only routing, but requires approval to transmit
source content. A plausible excerpt cannot prove visual completeness, table
alignment, icon associations, or coverage beyond the excerpt.

The [ambiguity gate](https://github.com/misbahsy/doc-router/blob/8977d2ba1fd672fbbc85f01e630a2d5de6a406aa/crates/doc-router-jev/src/judge.rs)
focuses on encoding and mixed findings rather than columns/tables. That fits
text readability, not the full hotel-facts contract. Native extraction overhead
is still paid even when the gate declines Jev; reuse existing representations.

## Do not copy these defaults unchanged

- The [runner](https://github.com/misbahsy/doc-router/blob/8977d2ba1fd672fbbc85f01e630a2d5de6a406aa/crates/doc-router/src/run.rs)
  retries the whole document after a failed leg. Retain successful stages and
  ambiguous attempt handles instead of replaying paid inference automatically.
- Non-strict Jev failures fall back to heuristic verdicts. Service failure must
  not become evidence that native extraction is sufficient.
- `split.rs` drops annotations and leaves unmapped indexes unchanged;
  `merge.rs` permits duplicate pages. Require complete, unique physical IDs and
  preserve annotation-derived facts and context.
- A correct routing label cannot fix the native extractor's documented
  watermark-text suppression. Evaluate extraction as well as classification.
- A floating model alias and a demo cutoff are not a calibrated acceptance policy.

## Preferred next step

The [Databricks reference](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document)
documents 1-indexed `pageRange`, for example `1,3,5-10`. Verify returned page IDs
before reassembly. Version 2.0 descriptions are figure-only; `'*'` and `'figure'`
are equivalent. Disabling them is not automatically safe for visual facts.

E25 completed the saved-artifact rehearsal, exposing substantial discrepancies
and visual-evidence differences on proposed native pages. It did not establish
which pages can safely skip managed parsing. Source-backed selection and a
bounded pageRange capability test come before any live cost-saving claim.

Compare fixed rules and Jev with the same extractor, merge, schema, Precision
mode, and evaluation. Share inference when routes are identical. Include all
overhead and use unseen layouts. See [our measured outcomes](results.md).
