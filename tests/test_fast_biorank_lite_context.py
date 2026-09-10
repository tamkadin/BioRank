import tempfile
import unittest
from pathlib import Path

from BioRank.BioRank import BioRankCancerGeneRanking
from BioRank.optimization.ablation_config import (
    ABLATION_MODE_FULL,
    ABLATION_MODE_WITHOUT_ANNOTATION,
    ablation_pipeline_config,
)
from BioRank.optimization.fast_biorank_lite import FastBioRankLiteContext


class FastBioRankLiteContextTest(unittest.TestCase):
    def test_full_mode_matches_standard_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._write_inputs(Path(tmp), include_annotation=True)
            self._assert_matches_standard_pipeline(
                paths,
                ABLATION_MODE_FULL,
                alpha=0.35,
                beta=0.65,
            )

    def test_without_annotation_matches_standard_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._write_inputs(Path(tmp), include_annotation=False)
            self._assert_matches_standard_pipeline(
                paths,
                ABLATION_MODE_WITHOUT_ANNOTATION,
                alpha=0.0,
                beta=0.65,
            )

    def _assert_matches_standard_pipeline(self, paths, ablation_mode, alpha, beta):
        config = ablation_pipeline_config(ablation_mode)
        fast = dict(FastBioRankLiteContext(paths, config).run(alpha, beta))

        runner = BioRankCancerGeneRanking(
            ppi_file_path=paths["ppi_file_path"],
            co_expression_file_path=paths.get("co_expression_file_path"),
            seed_file_path=paths["seed_file_path"],
            secondary_seed_file_path=paths.get("secondary_seed_file_path"),
            map__gene__ontologies_file_path=paths.get("map__gene__ontologies_file_path"),
            disease_ontology_file_path=paths.get("disease_ontology_file_path"),
            matrix_aggregation_policy=config["matrix_aggregation_policy"],
            personalization_vector_creation_policies=config["personalization_vector_creation_policies"],
            personalization_vector_aggregation_policy="Sum",
            alpha=alpha,
            beta=beta,
            network_weight_flag=config["network_weight_flag"],
            algorithm="biorank_lite",
            auto_run=False,
        )
        runner.prepare_network()
        runner.execute_ranking()
        standard = dict(runner.ranked_list)

        self.assertEqual(set(standard), set(fast))
        for gene, score in standard.items():
            self.assertAlmostEqual(fast[gene], score, places=12)

    def _write_inputs(self, folder, include_annotation):
        ppi_path = folder / "ppi.tsv"
        ppi_path.write_text(
            "\n".join(
                [
                    "Source\tTarget\tWeight",
                    "A\tB\t1.0",
                    "B\tC\t2.0",
                    "C\tD\t1.5",
                    "D\tA\t0.5",
                    "B\tD\t0.7",
                ]
            ),
            encoding="utf-8",
        )
        co_expression_path = folder / "co_expression.tsv"
        co_expression_path.write_text(
            "\n".join(
                [
                    "Source\tTarget\tWeight",
                    "A\tC\t0.9",
                    "B\tD\t0.8",
                    "A\tD\t0.4",
                ]
            ),
            encoding="utf-8",
        )
        seed_path = folder / "seed.tsv"
        seed_path.write_text("A\nC\n", encoding="utf-8")
        secondary_seed_path = folder / "de.tsv"
        secondary_seed_path.write_text(
            "\n".join(
                [
                    "A\t1.0",
                    "B\t0.7",
                    "C\t0.5",
                    "D\t0.2",
                ]
            ),
            encoding="utf-8",
        )

        paths = {
            "ppi_file_path": str(ppi_path),
            "co_expression_file_path": str(co_expression_path),
            "seed_file_path": str(seed_path),
            "secondary_seed_file_path": str(secondary_seed_path),
        }

        if include_annotation:
            mapping_path = folder / "mapping.tsv"
            mapping_path.write_text(
                "\n".join(
                    [
                        "Gene\tTerm\tDB",
                        "A\tT1\tGO",
                        "B\tT1\tGO",
                        "C\tT2\tGO",
                        "D\tT3\tGO",
                    ]
                ),
                encoding="utf-8",
            )
            disease_path = folder / "disease.tsv"
            disease_path.write_text("Term\tDB\nT1\tGO\nT2\tGO\n", encoding="utf-8")
            paths["map__gene__ontologies_file_path"] = str(mapping_path)
            paths["disease_ontology_file_path"] = str(disease_path)

        return paths


if __name__ == "__main__":
    unittest.main()
