# Billing attribution before cost comparisons

`scripts/charge_attribution.py` reconciles already-observed usage in ordinary
Python. It makes no network or model calls. The accompanying tests use fabricated
records and prices, not customer charges. This is an attribution prototype, not
an invoice calculator, live monitor, or demonstration of equal-quality savings.

## Evidence chain

1. Attach real query tags through the supported execution interface. A SQL
   comment is not a query tag. Keep tag values free of document content and
   customer identifiers. Retain the submission handle and intended tags privately.
2. Verify the actual tags against the exact statement in query history. Merely
   constructing a tagged request does not prove propagation. Resume saved handles
   after interruption; do not repeat inference to obtain timing or billing data.
3. Establish the resource/run link actually present in usage records. A verified
   query tag does not by itself create a per-statement billing join. Supply only
   independently verified, uniquely scoped run-to-cohort bindings.
4. Reconcile signed usage and effective list prices. Report unallocated rows,
   missing rates, and pending components separately from attributed totals.
5. Compare costs only for matched, accepted outputs on the same compute path,
   with common preprocessing counted once and supporting work accounted for.

`system.billing.usage` is updated throughout the day. Records are typically
available within 12 hours, not guaranteed in real time; new workspaces can take
longer. Twelve hours is neither a completeness guarantee nor a mandatory wait.
Observation queries and warehouse startup can themselves incur charges that
arrive later. An empty result is not evidence that an experiment was free.

## Input and output contract

The public tests show the complete minimal dictionaries. A caller must normalize
and validate its private source data before passing it to this prototype:

- Usage rows include account, workspace, SKU, cloud, unit, signed quantity,
  timezone-aware start/end, record type, origin product and run metadata.
- Prices contain the same account/SKU/cloud/unit, currency, effective interval
  and an `effective_list_rate` decimal string. This normalized field is supplied
  by the caller; the module does not discover a platform price-table schema.
- Bindings contain `workspace_id`, `key`, string `values`, `cohort` and
  `compute_path`. Only unique `job_run_id` bindings are accepted. Use one verified
  account scope per reconciliation; bindings do not include an account key.
- Requirements list each expected cohort/component/compute-path combination.
  `tags_verified` is an externally established assertion, not a check performed
  by the module. Caller labels and mappings are not authenticated here.

`reconcile(rows, prices, bindings)` returns per-record decisions, grouped USD
list-price totals, duplicate and unresolved counts. Quantities and rates use
decimal strings; floats and non-finite values are rejected. Arithmetic uses a
100-significant-digit decimal context, adequate for the bounded billing inputs
in the tests but not a guarantee for arbitrarily large inputs.

Originals, negative retractions and positive restatements are retained, including
corrections sharing a record ID. Deduplication uses the entire normalized row,
not the ID alone. Different normalization or extra fields can prevent duplicate
detection; input normalization remains the caller's responsibility.

A price must match account, SKU, cloud, unit, USD and the entire usage interval.
Missing/overlapping prices remain unresolved; the prototype does not prorate an
interval crossing a rate change. Effective list cost is not an invoice amount:
discounts, credits, taxes and other costs are outside this module.

Warehouse-only records are always unresolved, even if a caller supplies an
asserted isolation hash. This implementation has no validated shared-warehouse
allocation method and never divides a charge across strategies by elapsed time.
An ambiguous job binding likewise contributes to no strategy total.

`attribution_gate` requires verified tags, explicit component requirements,
positive reconciled usage for each requirement, and no unresolved rows in the
supplied scope. A missing or net-zero component does not prove mapping readiness;
this conservative rule is not a claim that legitimate zero charges cannot occur.
Unrelated unallocated rows in the supplied scope also block this gate.

Even a passing gate returns `complete_cost=False` and
`paid_execution_authorized=False`. Separately require source-backed quality
evaluation, a frozen runner, spend limits and execution/data-boundary approval.
Typed output and literal matching do not establish semantic correctness.

## Run the synthetic checks

```sh
python3 -m unittest discover -s tests -p 'test_charge_attribution.py'
```

The tests cover decimal pricing, corrections, duplicates, absent records,
ambiguous bindings, rejected warehouse allocation, price matching, component
coverage and separation of mapping readiness from execution permission. They
do not reproduce real charges or verify any live workspace.
