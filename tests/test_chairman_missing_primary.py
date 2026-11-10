"""Missing chairman mappings must not silently recycle recoverable VISCA slots."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import application.chairman_presets as chairman
from application.preset_service import PresetService


class MissingChairmanPrimary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.primary = Path(self.temp.name) / 'chairman_presets.json'
        self.backup = self.primary.with_suffix('.bak')
        override = patch.object(chairman, 'CHAIRMAN_PRESETS_FILE', self.primary)
        override.start()
        self.addCleanup(override.stop)

    def test_missing_primary_recovers_backup_without_recycling_slot(self):
        self.backup.write_text('{"Existing person": 10}', encoding='utf-8')
        presets = PresetService()
        self.assertEqual(presets.get_preset_for_name('Existing person'), 10)
        self.assertEqual(presets.assign_slot('New person'), (11, True))
        self.assertFalse(self.primary.exists(), 'reading must not create a replacement file')
        self.assertEqual(json.loads(self.backup.read_text()), {'Existing person': 10})

    def test_primary_wins_over_stale_backup(self):
        self.primary.write_text('{"Current":11}', encoding='utf-8')
        self.backup.write_text('{"Previous":10}', encoding='utf-8')
        self.assertEqual(chairman.load_chairman_presets(), {'Current':11})

    def test_intentionally_empty_primary_is_not_resurrected(self):
        self.primary.write_text('{}', encoding='utf-8')
        self.backup.write_text('{"Previous":10}', encoding='utf-8')
        self.assertEqual(chairman.load_chairman_presets(), {})

    def test_genuinely_new_install_has_no_mapping_or_writes(self):
        self.assertEqual(chairman.load_chairman_presets(), {})
        self.assertEqual(list(self.primary.parent.iterdir()), [])

    def test_backup_runs_existing_slot_validation(self):
        self.backup.write_text('{"Valid":10,"Duplicate":10,"Outside":90,"String":"11"}', encoding='utf-8')
        self.assertEqual(chairman.load_chairman_presets(), {'Valid':10})

    def test_invalid_backup_returns_empty_without_changing_evidence(self):
        for text in ['{', '[]', '{"Outside":0}']:
            with self.subTest(text=text):
                self.backup.write_text(text, encoding='utf-8')
                self.assertEqual(chairman.load_chairman_presets(), {})
                self.assertEqual(self.backup.read_text(), text)

    def test_later_explicit_save_preserves_recovered_mapping(self):
        self.backup.write_text('{"Existing":10}', encoding='utf-8')
        presets = PresetService()
        self.assertEqual(presets.assign_slot('New'), (11, True))
        self.assertTrue(presets.persist())
        self.assertEqual(json.loads(self.primary.read_text()), {'Existing':10,'New':11})
        self.assertEqual(json.loads(self.backup.read_text()), {'Existing':10})


if __name__ == '__main__':
    unittest.main()
