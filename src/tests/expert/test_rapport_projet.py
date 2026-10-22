import io
import json
import unittest
import zipfile

import pandas as pd

from src.core.dictionnaire import initial_dictionary, records
from src.etape3_corriger.pipeline import pipeline
from src.expert.rapport_projet import project_archive


class ReportingTests(unittest.TestCase):
    def test_archive_preserves_source_and_exports_results(self):
        source = b"id,value\n001,4\n001,4\n"
        raw = pd.read_csv(io.BytesIO(source), dtype={"id": "string"})
        cleaned, rejects, _ = pipeline(raw, records(initial_dictionary(raw)), [], {}, deduplicate=True)
        report = {"cadrage": {"project_name": "Test"}, "source": "test.csv", "objectif": "Explorer",
                  "decision": "GO avec réserves", "justification_decision": "Période limitée", "conclusions": "À compléter",
                  "dashboard": {"charts": [], "roles": {}, "filters": [], "dayfirst": False}}
        versions = [{"cleaned": cleaned.to_csv(index=False), "rejects": rejects.to_csv(index=False), "recipe": {"deduplicate": True}}]
        bundle = project_archive(source, cleaned, rejects, report, versions)
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            self.assertEqual(archive.read("data/raw/source.csv"), source)
            self.assertEqual(json.loads(archive.read("reports/project.json"))["decision"], "GO avec réserves")
            self.assertIn("history/v001/recipe.json", archive.namelist())
            self.assertIn("001", archive.read("data/processed/current.csv").decode())
