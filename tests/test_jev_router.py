import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from jev_router import MODEL, build_request, eligible_methods, recommendations, safe_record


class JevRouterTests(unittest.TestCase):
    def test_content_fields_refused(self):
        for key in ('text', 'url', 'filename', 'hotel', 'source_sha256', 'notes'):
            with self.assertRaises(ValueError):
                safe_record({'scope':'page', key:'do not transmit'})

    def test_string_in_numeric_field_refused(self):
        with self.assertRaises(ValueError):
            safe_record({'scope':'page','native_characters':'secret content'})

    def test_unknown_is_not_zero(self):
        record = safe_record({'scope':'page','native_characters':None})
        self.assertIsNone(record['native_characters'])
        self.assertIn('native_text_precision', eligible_methods(record))

    def test_raster_only_cannot_choose_native(self):
        request = build_request([{'scope':'page','native_characters':0}])
        self.assertNotIn('native_text_precision', request['questions']['route_0']['criteria'])
        self.assertNotIn('native_layout_precision', request['questions']['route_0']['criteria'])

    def test_sparse_live_text_does_not_force_ocr(self):
        request = build_request([{'scope':'page','native_characters':25,'native_text_available':True}])
        self.assertIn('native_text_precision', request['questions']['route_0']['criteria'])

    def test_visual_risk_requires_visual_capable_candidate(self):
        methods = eligible_methods({'visual_fact_risk':True})
        self.assertEqual(set(methods), {'managed_parse_precision','visual_review'})

    def test_arithmetic_invalid_values_refused(self):
        for value in (float('nan'), float('inf'), -1, True):
            with self.assertRaises(ValueError):
                safe_record({'scope':'page','image_count':value})

    def test_no_confidence_grants_dispatch(self):
        request = build_request([{'scope':'page','native_characters':0}])
        response = {'model':MODEL, 'answers':{'route_0':{'type':'choice','choice':'visual_review',
            'probabilities':{'visual_review':1, 'managed_parse_precision':0},'confidence':1}},
            'usage':{'input_tokens':100,'output_tokens':5}}
        result = recommendations(request, response)
        self.assertFalse(result['recommendations'][0]['dispatch_authorized'])
        self.assertFalse(result['savings_proven'])

    def test_extra_answer_refused(self):
        request = build_request([{'scope':'document'}])
        with self.assertRaises(ValueError):
            recommendations(request, {'model':MODEL, 'answers':{}})

    def test_bounded_request_and_full_scope(self):
        request = build_request([{'scope':'document'}, {'scope':'page','page_ordinal':1}])
        self.assertEqual(len(request['questions']), 2)
        self.assertTrue(request['state']['constraints']['all_source_pages_required'])
        with self.assertRaises(ValueError):
            build_request([{'scope':'page'}]*33)

    def test_no_model_needed_for_only_one_allowed_route(self):
        with self.assertRaisesRegex(ValueError, 'deterministically'):
            build_request([{'scope':'page','source_readable':False}])


if __name__ == '__main__':
    unittest.main()
