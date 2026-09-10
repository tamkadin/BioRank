import gzip
import tempfile
import threading
import unittest
from pathlib import Path

from biorank_ui.preprocessing_dialog import build_preprocessing_dialog_config
from biorank_ui.service import BackendService


class _PreprocessingState:
    def __init__(self):
        self.file_paths = {}
        self.file_statuses = {}
        self.preprocessing_statuses = {1: "Pending", 2: "Pending", 3: "Pending", 4: "Pending"}


class PreprocessingWorkflowTest(unittest.TestCase):
    def test_dialog_configs_expose_all_fields_without_sequential_browsing(self):
        file_paths = {"ontology_map": "ontology.tsv", "seed": "seed.tsv"}
        expected_keys = {
            1: {
                "go_file_path", "kegg_file_path", "reactome_file_path",
                "uniprot_mapping_path", "kegg_mapping_path", "output_file_path",
            },
            2: {"ontology_file_path", "seed_file_path", "output_file_path"},
            3: {
                "sample_sheet_file_path", "manifest_file_path",
                "tcga_directory_path", "output_dir_path",
            },
            4: {
                "tumor_file_path", "control_file_path", "identifier_file_path",
                "de_output_file_path", "coexpression_output_file_path",
            },
        }

        for step_index, keys in expected_keys.items():
            config = build_preprocessing_dialog_config(step_index, "BRCA", file_paths)
            self.assertEqual({field["key"] for field in config["fields"]}, keys)

        step_two = build_preprocessing_dialog_config(2, "BRCA", file_paths)
        defaults = {field["key"]: field["default"] for field in step_two["fields"]}
        self.assertTrue(defaults["ontology_file_path"].endswith("ontology.tsv"))
        self.assertTrue(defaults["seed_file_path"].endswith("seed.tsv"))
        self.assertTrue(defaults["output_file_path"].endswith("TCGA-BRCA_disease_ontologies.txt"))

    def test_ontology_and_disease_ontology_steps_create_ranker_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            go_file = root / "go.gaf"
            kegg_file = root / "kegg.tsv"
            reactome_file = root / "reactome.tsv"
            uniprot_mapping = root / "uniprot_ensembl.tsv"
            kegg_mapping = root / "kegg_uniprot.tsv"
            ontology_output = root / "ontology.tsv"
            seed_file = root / "seed.tsv"
            disease_output = root / "disease_ontology.txt"

            go_file.write_text("DB\tP1\tx\tx\tGO:0001\tx\tEXP\tx\tP\n", encoding="utf-8")
            kegg_file.write_text("path:hsa0001\thsa:1\n", encoding="utf-8")
            reactome_file.write_text("ENSG2\tR-HSA-1\tx\tx\tTAS\n", encoding="utf-8")
            uniprot_mapping.write_text("uniprot\tensembl\nP1\tENSG1\n", encoding="utf-8")
            kegg_mapping.write_text("kegg\tuniprot\nhsa:1\tP1\n", encoding="utf-8")
            seed_file.write_text("ENSG1\n", encoding="utf-8")

            state = _PreprocessingState()
            service = BackendService(state)
            service.run_preprocessing_step(
                1,
                {
                    "go_file_path": str(go_file),
                    "kegg_file_path": str(kegg_file),
                    "reactome_file_path": str(reactome_file),
                    "uniprot_mapping_path": str(uniprot_mapping),
                    "kegg_mapping_path": str(kegg_mapping),
                    "output_file_path": str(ontology_output),
                },
                lambda _progress, _status: None,
                threading.Event(),
            )
            service.run_preprocessing_step(
                2,
                {
                    "ontology_file_path": str(ontology_output),
                    "seed_file_path": str(seed_file),
                    "output_file_path": str(disease_output),
                },
                lambda _progress, _status: None,
                threading.Event(),
            )

            self.assertEqual(ontology_output.read_text(encoding="utf-8").splitlines()[0], "gene_id\tterm_id\tDB")
            self.assertEqual(disease_output.read_text(encoding="utf-8").splitlines()[0], "Term_ID\tDB")
            self.assertEqual(state.file_paths["ontology_map"], str(ontology_output.resolve()))
            self.assertEqual(state.file_paths["disease_ontology"], str(disease_output.resolve()))
            self.assertEqual(state.preprocessing_statuses[1], "Completed")
            self.assertEqual(state.preprocessing_statuses[2], "Completed")

    def test_tcga_step_uses_manifest_and_creates_tumor_control_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rna_dir = root / "rna"
            output_dir = root / "tables"
            sample_sheet = root / "sample_sheet.tsv"
            manifest = root / "manifest.tsv"

            sample_sheet.write_text(
                "File ID\tFile Name\tData Category\tData Type\tProject ID\tCase ID\tSample ID\n"
                "tumor-id\ttumor.tsv.gz\tRNA\tCounts\tTCGA-TEST\tcase-1\tTCGA-AA-0001-01A\n"
                "control-id\tcontrol.tsv.gz\tRNA\tCounts\tTCGA-TEST\tcase-2\tTCGA-AA-0002-11A\n"
                "ignored-id\tignored.tsv.gz\tRNA\tCounts\tTCGA-TEST\tcase-3\tTCGA-AA-0003-01A\n",
                encoding="utf-8",
            )
            manifest.write_text("id\tfilename\ntumor-id\ttumor.tsv.gz\ncontrol-id\tcontrol.tsv.gz\n", encoding="utf-8")
            for file_id, file_name, value in (
                ("tumor-id", "tumor.tsv.gz", "10"),
                ("control-id", "control.tsv.gz", "2"),
            ):
                folder = rna_dir / file_id
                folder.mkdir(parents=True)
                with gzip.open(folder / file_name, "wt", encoding="utf-8") as fp:
                    fp.write(f"ENSG000001.1\t{value}\n")

            state = _PreprocessingState()
            service = BackendService(state)
            service.run_preprocessing_step(
                3,
                {
                    "sample_sheet_file_path": str(sample_sheet),
                    "manifest_file_path": str(manifest),
                    "tcga_directory_path": str(rna_dir),
                    "output_dir_path": str(output_dir),
                },
                lambda _progress, _status: None,
                threading.Event(),
            )

            self.assertTrue((output_dir / "TCGA-TEST__tumor.tsv").is_file())
            self.assertTrue((output_dir / "TCGA-TEST__control.tsv").is_file())
            self.assertNotIn("ignored-id", (output_dir / "TCGA-TEST__tumor.tsv").read_text(encoding="utf-8"))
            self.assertEqual(state.preprocessing_statuses[3], "Completed")

    def test_expression_step_accepts_tcga_control_table_and_records_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tumor = root / "tumor.tsv"
            control = root / "control.tsv"
            identifiers = root / "identifiers.txt"
            de_output = root / "de.tsv"
            coexpression_output = root / "coexpression.tsv"

            tumor.write_text(
                "Gene_ID\tT1\tT2\tT3\n"
                "ENSG1.1\t100\t120\t140\n"
                "ENSG2.1\t10\t20\t30\n",
                encoding="utf-8",
            )
            control.write_text(
                "Gene_ID\tC1\tC2\tC3\n"
                "ENSG1.1\t1\t2\t3\n"
                "ENSG2.1\t8\t10\t12\n",
                encoding="utf-8",
            )
            identifiers.write_text("ENSG1\nENSG2\n", encoding="utf-8")

            state = _PreprocessingState()
            service = BackendService(state)
            service.run_preprocessing_step(
                4,
                {
                    "tumor_file_path": str(tumor),
                    "control_file_path": str(control),
                    "identifier_file_path": str(identifiers),
                    "de_output_file_path": str(de_output),
                    "coexpression_output_file_path": str(coexpression_output),
                },
                lambda _progress, _status: None,
                threading.Event(),
            )

            self.assertTrue(de_output.is_file())
            self.assertEqual(coexpression_output.read_text(encoding="utf-8").splitlines()[0], "u\tv\tscore")
            self.assertEqual(state.file_paths["de_genes"], str(de_output.resolve()))
            self.assertEqual(state.file_paths["coexpression"], str(coexpression_output.resolve()))
            self.assertEqual(state.preprocessing_statuses[4], "Completed")


if __name__ == "__main__":
    unittest.main()
