import unittest
from replay_refresh import decide, KEYS


class RefreshTests(unittest.TestCase):
    def test_only_refreshing_failed_obligation_changes_cached_approval(self):
        cached = {k: {'verified': True} for k in KEYS}
        for failed in KEYS:
            current = {k: {'verified': k != failed} for k in KEYS}
            self.assertTrue(decide(cached, current, ()))
            self.assertFalse(decide(cached, current, (failed,)))
            self.assertTrue(decide(cached, current, tuple(k for k in KEYS if k != failed)))

    def test_bad_cached_evidence_is_not_silently_replaced(self):
        cached = {k: {'verified': False} for k in KEYS}
        current = {k: {'verified': True} for k in KEYS}
        self.assertFalse(decide(cached, current, KEYS[:2]))
        self.assertTrue(decide(cached, current, KEYS))

    def test_unknown_obligation_rejected(self):
        with self.assertRaises(ValueError):
            decide({}, {}, ('unknown',))


if __name__ == '__main__':
    unittest.main()
