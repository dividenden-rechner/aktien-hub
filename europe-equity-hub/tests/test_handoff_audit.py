import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_europe_workbook import audit

ROOT = Path(__file__).resolve().parents[1]

class WorkbookAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary, cls.rows = audit(ROOT / 'input' / 'europa_aktien_hub_v0_5_boersenabgleich.xlsx')  # v0.7: Eingangsdaten liegen unter input/
    def test_source_rows(self):
        self.assertEqual(self.summary['existing_rows'], 422)
    def test_candidate_rows(self):
        self.assertEqual(self.summary['candidate_rows'], 580)
    def test_no_verified_candidates(self):
        self.assertEqual(self.summary['verified_candidates'], 0)
    def test_queue_count(self):
        self.assertEqual(len(self.rows), 580)

if __name__ == '__main__':
    unittest.main()
