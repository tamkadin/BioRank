import os
import csv

from data_preprocessing.enrichment_pipeline.enrichment_analysis import EnrichmentAnalysis
from data_preprocessing.enrichment_pipeline.p_value_correction import compute_p_value_fdr_correction

class DiseaseOntologies:
    def __init__(self, ontology_graph_file_path, disease_seed_file_path, output_file_path):
        self.ontology_graph_file_path = ontology_graph_file_path
        self.disease_seed_file_path = disease_seed_file_path
        self.output_file_path = output_file_path
        self.p_value_threshold = 1e-5

    def __load_ontology_graph__(self):
        self.map__db__gene_id__term_ids = {}
        self.map__db__term_id__gene_ids = {}

        with open(self.ontology_graph_file_path, "r") as fp:
            csv_reader = csv.reader(fp, delimiter="\t")
            for index, row in enumerate(csv_reader):
                if index == 0:
                    continue

                gene_name, term, db_name = row[0], row[1], row[2]

                self.map__db__gene_id__term_ids.setdefault(db_name, {}).setdefault(gene_name, set()).add(term)
                self.map__db__term_id__gene_ids.setdefault(db_name, {}).setdefault(term, set()).add(gene_name)

    def __load_seed__(self, file_path):
        with open(file_path, "r") as f:
            return {row[0] for row in csv.reader(f, delimiter="\t")}

    def run(self):
        # Skip if file already exists
        if os.path.exists(self.output_file_path):
            print(f"⚠️ File already exists: {self.output_file_path} — skipping.")
            return

        self.__load_ontology_graph__()
        disease_genes = self.__load_seed__(self.disease_seed_file_path)

        disease_ontologies = [["Term_ID", "DB"]]

        for db_name in self.map__db__gene_id__term_ids:
            gene2term = self.map__db__gene_id__term_ids[db_name]
            term2gene = self.map__db__term_id__gene_ids[db_name]

            enrichment = EnrichmentAnalysis(gene2term, term2gene, disease_genes)
            raw_pvals = enrichment.get_enirchment_analysis()

            fdr_passed = compute_p_value_fdr_correction(raw_pvals, p_value_threshold=self.p_value_threshold)

            for term in fdr_passed:
                disease_ontologies.append([term, db_name])

        with open(self.output_file_path, "w", newline="") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerows(disease_ontologies)

        print(f"✅ Disease-specific ontology saved: {self.output_file_path}")
