"""Measurement-contract tests, not benchmark experiments."""
import json
import unittest
from probe import classify_read

class ReadbackContract(unittest.TestCase):
    def test_acknowledgement_is_not_readback(self):
        self.assertEqual(classify_read(200, 'Successfully upload post', 'm', 7), 'unresolved_invalid_json')
    def test_empty_timeline_is_not_success(self):
        for body in ('[]', '{}'):
            self.assertEqual(classify_read(200, body, 'm', 7), 'not_observed')
    def test_wrong_creator_is_detected(self):
        body = json.dumps([{'text': 'm', 'creator': {'user_id': '8'}}])
        self.assertEqual(classify_read(200, body, 'm', 7), 'creator_mismatch')
    def test_exact_marker_and_creator_are_required(self):
        body = json.dumps([{'text': 'm', 'creator': {'user_id': '7'}}])
        self.assertEqual(classify_read(200, body, 'm', 7), 'verified_readback')
        self.assertEqual(classify_read(200, body, 'other', 7), 'not_observed')
    def test_timeout_is_unknown_not_safe(self):
        self.assertEqual(classify_read(None, '', 'm', 7), 'unresolved_read_error')
    def test_malformed_payload_is_unknown(self):
        for body in ('null', '[7]', '[{"text":"m"}]'):
            self.assertEqual(classify_read(200, body, 'm', 7), 'unresolved_invalid_schema')

if __name__ == '__main__':
    unittest.main()
