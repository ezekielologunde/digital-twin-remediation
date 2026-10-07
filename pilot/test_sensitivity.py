import unittest
from analyze_sensitivity import endpoint

class EndpointTests(unittest.TestCase):
    def test_insufficient_is_unknown(self):
        self.assertIsNone(endpoint([], 2, 2))

    def test_later_recovery_does_not_leak_into_prefix(self):
        obs = [{'elapsed_s': 1, 'classification': 'unresolved_read_error'},
               {'elapsed_s': 3, 'classification': 'verified_readback'}]
        self.assertFalse(endpoint(obs, 2, 1))
        self.assertTrue(endpoint(obs, 4, 1))

    def test_mismatch_overrides_later_success(self):
        obs = [{'elapsed_s': 1, 'classification': 'creator_mismatch'},
               {'elapsed_s': 2, 'classification': 'verified_readback'}]
        self.assertFalse(endpoint(obs, 2, 1))

    def test_terminal_count_and_boundary(self):
        obs = [{'elapsed_s': 1, 'classification': 'unresolved_read_error'},
               {'elapsed_s': 2, 'classification': 'verified_readback'}]
        self.assertTrue(endpoint(obs, 2, 1))
        self.assertFalse(endpoint(obs, 2, 2))
