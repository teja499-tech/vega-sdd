import tempfile
import unittest
from pathlib import Path
from store import Store
class StorageTests(unittest.TestCase):
    def test_persistence_and_sql_literal(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/'data.db'); s=Store(p)
            s.create("x'); DROP TABLE incident; --")
            self.assertEqual(len(Store(p).list()),1)
    def test_atomic_update_and_not_found(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(str(Path(d)/'data.db')); item=s.create('incident')
            self.assertTrue(s.update(item['id'],'resolved'))
            self.assertFalse(s.update(999,'resolved'))
            self.assertEqual(s.list()[0]['status'],'resolved')
