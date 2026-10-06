import unittest
from paired_pilot import empty_timeline

class ResetMeasurement(unittest.TestCase):
    def test_http_failure_cannot_prove_reset(self):
        self.assertFalse(empty_timeline(500,'[]'))
        self.assertFalse(empty_timeline(None,''))
    def test_nonempty_and_malformed_fail(self):
        for body in ('[{"text":"old"}]','null','false','invalid'):
            self.assertFalse(empty_timeline(200,body))
    def test_both_empty_encodings_pass(self):
        self.assertTrue(empty_timeline(200,'[]'))
        self.assertTrue(empty_timeline(200,'{}'))

if __name__=='__main__':
    unittest.main()
