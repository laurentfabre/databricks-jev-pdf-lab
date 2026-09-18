import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from textpage_reuse import View, extract_views, compare_trials, digest


class FakePage:
    def __init__(self, identity="first"):
        self.identity = identity
        self.created = []

    def get_textpage(self, *, flags, clip):
        value = (self.identity, flags, clip)
        self.created.append(value)
        return value

    def get_text(self, format, **kwargs):
        if "textpage" in kwargs:
            assert "flags" not in kwargs and "clip" not in kwargs
            identity, flags, clip = kwargs["textpage"]
        else:
            identity, flags, clip = self.identity, kwargs["flags"], kwargs["clip"]
        return [identity, format, flags, clip, kwargs["sort"]]


def trials():
    return [{"doc_id": 1, "workload": w, "repeat": r, "lane": lane,
             "pages": [{"page": 1, "sha256": {v: digest(v) for v in views}}],
             "extract_seconds": 2 if lane == "independent" else 1,
             "worker_seconds": 3, "process_wall_seconds": 4, "peak_rss_bytes_sampled": 100}
            for w, views in [("audit_pair", ("sorted_text", "sorted_words")),
                             ("routing_views", ("native_text", "sorted_text", "native_words", "text_layout"))]
            for r in range(4) for lane in ("independent", "shared")]


class ReuseTests(unittest.TestCase):
    def test_exact_views_and_one_creation(self):
        page = FakePage()
        views = (View("text", "text", 3), View("words", "words", 3, True))
        self.assertEqual(extract_views(page, views, shared=False), extract_views(page, views, shared=True))
        self.assertEqual(len(page.created), 1)

    def test_flags_do_not_share(self):
        page = FakePage()
        extract_views(page, (View("a", "text", 3), View("b", "dict", 7)), shared=True)
        self.assertEqual(len(page.created), 2)

    def test_clips_do_not_share(self):
        page = FakePage()
        views = (View("a", "text", 3), View("b", "words", 3, clip=(0, 0, 50, 50)))
        self.assertEqual(extract_views(page, views, shared=False), extract_views(page, views, shared=True))
        self.assertEqual(len(page.created), 2)

    def test_pages_and_calls_do_not_share(self):
        views = (View("a", "text", 3),)
        first, second = FakePage(), FakePage("second")
        self.assertNotEqual(extract_views(first, views, shared=True), extract_views(second, views, shared=True))
        extract_views(first, views, shared=True)
        self.assertEqual(len(first.created), 2)

    def test_duplicate_names_rejected(self):
        with self.assertRaises(ValueError):
            extract_views(FakePage(), [View("a", "text", 3)] * 2, shared=True)

    def test_invalid_clips(self):
        for clip in ((0, 0, 0, 1), (0, 0, float("inf"), 1), (0, 1)):
            with self.assertRaises(ValueError):
                View("a", "text", 3, clip=clip)

    def test_all_measurements_required(self):
        with self.assertRaises(ValueError):
            compare_trials(trials()[:-1], {1: 1})

    def test_duplicate_measurement_rejected(self):
        values = trials()
        with self.assertRaises(ValueError):
            compare_trials(values + [values[0]], {1: 1})

    def test_changed_word_or_coordinate_rejected(self):
        values = trials()
        values[-1]["pages"][0]["sha256"]["native_words"] = digest(["same word", 1.00001])
        with self.assertRaises(ValueError):
            compare_trials(values, {1: 1})

    def test_missing_view_rejected(self):
        values = trials()
        for value in values:
            value["pages"][0]["sha256"].pop("sorted_text")
        with self.assertRaises(ValueError):
            compare_trials(values, {1: 1})

    def test_bad_page_coverage_rejected(self):
        with self.assertRaises(ValueError):
            compare_trials(trials(), {1: 2})

    def test_exact_comparison_and_aggregate(self):
        result = compare_trials(trials(), {1: 1})
        self.assertTrue(result["exact_output_equivalence"])
        self.assertEqual(result["measurement_count"], 16)
        self.assertEqual(result["totals"][0]["ratio_of_summed_medians"], 2)

    def test_hash_preserves_whitespace_order_and_coordinates(self):
        for left, right in [("€ 70/95", "€70/95"), (["a", "b"], ["b", "a"]),
                            ([1.1], [1.1000001])]:
            self.assertNotEqual(digest(left), digest(right))
        self.assertEqual(digest({"b": 2, "a": 1}), digest({"a": 1, "b": 2}))


if __name__ == "__main__":
    unittest.main()
