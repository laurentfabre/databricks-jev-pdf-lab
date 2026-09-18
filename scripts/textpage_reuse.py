"""Page-scoped extraction reuse; no PDF dependencies or inference at import time.

Only views with identical flags and clip share a TextPage. Never carry a cached
TextPage between pages, document mutations, processes or extraction calls.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import statistics


@dataclass(frozen=True)
class View:
    name: str
    format: str
    flags: int
    sort: bool = False
    clip: tuple | None = None

    def __post_init__(self):
        if not self.name or self.format not in ("text", "words", "dict"):
            raise ValueError("Explicit name and supported text view required")
        if type(self.flags) is not int or self.flags < 0 or type(self.sort) is not bool:
            raise ValueError("Invalid flags/sort")
        if self.clip is not None:
            if not isinstance(self.clip, tuple) or len(self.clip) != 4:
                raise ValueError("Clip must be a four-coordinate tuple")
            if not all(type(x) in (int, float) and math.isfinite(x) for x in self.clip):
                raise ValueError("Invalid clip coordinates")
            if self.clip[0] >= self.clip[2] or self.clip[1] >= self.clip[3]:
                raise ValueError("Clip must be nonempty")


def extract_views(page, views, *, shared):
    """Same API outputs in both lanes; creation costs are included by caller."""
    views = tuple(views)
    if len({v.name for v in views}) != len(views):
        raise ValueError("Duplicate output names")
    cache = {}
    result = {}
    for view in views:
        if shared:
            key = (view.flags, view.clip)
            if key not in cache:
                cache[key] = page.get_textpage(flags=view.flags, clip=view.clip)
            # flags/clip belong to get_textpage; passing them here silently does
            # nothing in PyMuPDF. Keep them out of this call deliberately.
            result[view.name] = page.get_text(view.format, sort=view.sort,
                                              textpage=cache[key])
        else:
            result[view.name] = page.get_text(view.format, flags=view.flags,
                                              clip=view.clip, sort=view.sort)
    return result


def workload_views(fitz, workload):
    if workload == "audit_pair":
        return (View("sorted_text", "text", fitz.TEXTFLAGS_TEXT, True),
                View("sorted_words", "words", fitz.TEXTFLAGS_WORDS, True))
    if workload == "routing_views":
        return (View("native_text", "text", fitz.TEXTFLAGS_TEXT),
                View("sorted_text", "text", fitz.TEXTFLAGS_TEXT, True),
                View("native_words", "words", fitz.TEXTFLAGS_WORDS),
                View("text_layout", "dict", fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES))
    raise ValueError("Unknown benchmark workload")


def digest(value):
    # Preserve strings, array order, every coordinate and all dictionary fields.
    # No rounding, normalization, dropped keys or whitespace stripping.
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def compare_trials(trials, expected_pages, repeats=4):
    index = {}
    workloads = ("audit_pair", "routing_views")
    lanes = ("independent", "shared")
    for trial in trials:
        key = (trial["doc_id"], trial["workload"], trial["repeat"], trial["lane"])
        if key in index:
            raise ValueError("Duplicate measurement identity")
        index[key] = trial
    wanted = {(d, w, r, lane) for d in expected_pages for w in workloads
              for r in range(repeats) for lane in lanes}
    if set(index) != wanted:
        raise ValueError("Missing or unexpected measurements")
    rows = []
    for doc_id, page_count in sorted(expected_pages.items()):
        for workload in workloads:
            first = index[(doc_id, workload, 0, "independent")]
            baseline = first["pages"]
            if [p["page"] for p in baseline] != list(range(1, page_count + 1)):
                raise ValueError("Page coverage/order mismatch")
            required_views = ({"sorted_text", "sorted_words"} if workload == "audit_pair"
                              else {"native_text", "sorted_text", "native_words", "text_layout"})
            for page in baseline:
                if set(page["sha256"]) != required_views:
                    raise ValueError("View coverage mismatch")
            for repeat in range(repeats):
                for lane in lanes:
                    trial = index[(doc_id, workload, repeat, lane)]
                    if trial["pages"] != baseline:
                        raise ValueError(f"Exact output mismatch for {doc_id}/{workload}/{repeat}/{lane}")
                    for field in ("extract_seconds", "worker_seconds", "process_wall_seconds"):
                        if not math.isfinite(trial[field]) or trial[field] <= 0:
                            raise ValueError("Invalid timing")
            by_lane = {}
            for lane in lanes:
                samples = [index[(doc_id, workload, r, lane)] for r in range(repeats)]
                by_lane[lane] = {
                    field: {"median": statistics.median(x[field] for x in samples),
                            "min": min(x[field] for x in samples),
                            "max": max(x[field] for x in samples)}
                    for field in ("extract_seconds", "worker_seconds", "process_wall_seconds",
                                  "peak_rss_bytes_sampled")}
            rows.append({"doc_id": doc_id, "workload": workload, "pages": page_count,
                         "exact_views_per_page": len(required_views), "all_repeats_equal": True,
                         "samples_per_lane": repeats, "lanes": by_lane,
                         "extract_speedup_ratio": by_lane["independent"]["extract_seconds"]["median"] /
                                                  by_lane["shared"]["extract_seconds"]["median"]})
    totals = []
    for workload in workloads:
        selected = [r for r in rows if r["workload"] == workload]
        times = {lane: sum(r["lanes"][lane]["extract_seconds"]["median"] for r in selected)
                 for lane in lanes}
        totals.append({"workload": workload, "pages": sum(expected_pages.values()),
                       "sum_document_medians_seconds": times,
                       "ratio_of_summed_medians": times["independent"] / times["shared"],
                       "kernel_seconds_saved": times["independent"] - times["shared"],
                       "not_end_to_end_or_tco": True})
    return {"documents": rows, "totals": totals, "exact_output_equivalence": True,
            "measurement_count": len(trials)}
