import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import biorank_ui.service as service_module
from biorank_ui.service import BackendService


class ServiceRankingOutputTest(unittest.TestCase):
    def test_enrich_ranking_output_adds_mapping_and_oncokb_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ranking_path = tmp_path / "ranking.tsv"
            mapping_path = tmp_path / "mapping.tsv"
            oncokb_path = tmp_path / "oncokb.csv"

            ranking_path.write_text(
                "GeneNames\tScore\nENSG000001\t0.9\nENSG000002\t0.1\n",
                encoding="utf-8",
            )
            mapping_path.write_text(
                "Gene stable ID\tGene name\nENSG000001\tTP53\nENSG000002\tGENE2\n",
                encoding="utf-8",
            )
            oncokb_path.write_text("Gene\nTP53\n", encoding="utf-8")

            original_mapping_path = service_module.GENE_MAPPING_PATH
            original_oncokb_path = service_module.ONCOKB_PATH
            service_module.GENE_MAPPING_PATH = str(mapping_path)
            service_module.ONCOKB_PATH = str(oncokb_path)
            try:
                state = SimpleNamespace()
                service = BackendService(state)

                service._enrich_ranking_output(str(ranking_path))
                service._load_ranking_into_state(str(ranking_path))
            finally:
                service_module.GENE_MAPPING_PATH = original_mapping_path
                service_module.ONCOKB_PATH = original_oncokb_path

            with ranking_path.open(newline="", encoding="utf-8-sig") as fp:
                rows = list(csv.DictReader(fp, delimiter="\t"))

            self.assertEqual(
                list(rows[0].keys()),
                ["Rank", "GeneNames", "GeneSymbol", "Score", "OncoKBHit"],
            )
            self.assertEqual(rows[0]["GeneSymbol"], "TP53")
            self.assertEqual(rows[0]["OncoKBHit"], "Yes")
            self.assertEqual(rows[1]["OncoKBHit"], "No")
            self.assertTrue(state.active_results[0]["oncokb_hit"])
            self.assertFalse(state.active_results[1]["oncokb_hit"])


if __name__ == "__main__":
    unittest.main()
