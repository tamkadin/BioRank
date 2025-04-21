import csv
import os

class OntologyGraph:
    def __init__(self,
                 GO_file_path,
                 KEGG_file_path,
                 Reactome_file_path,
                 output_file_path,
                 uniprot_mapping_path,
                 kegg_mapping_path):

        self.GO_file_path = GO_file_path
        self.KEGG_file_path = KEGG_file_path
        self.Reactome_file_path = Reactome_file_path
        self.output_ontology_network_path = output_file_path
        self.UniprotKB__Ensembl__mapping_file_path = uniprot_mapping_path
        self.KEGG__UniprotKB__mapping_file_path = kegg_mapping_path

    def __load_uniprot_mapping__(self):
        self.map__uniprotkb__ensembl_id = {}
        with open(self.UniprotKB__Ensembl__mapping_file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader, None)
            for row in reader:
                if len(row) >= 2:
                    self.map__uniprotkb__ensembl_id.setdefault(row[0], set()).add(row[1])

    def __load_KEGG_to_uniprot_mapping__(self):
        self.map__KEGG__uniprot_id = {}
        with open(self.KEGG__UniprotKB__mapping_file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            next(reader, None)
            for row in reader:
                if len(row) >= 2:
                    self.map__KEGG__uniprot_id.setdefault(row[0], set()).add(row[1])

    def __load_go__(self):
        self.map__ensembl_id__gene_ontologies = {}
        with open(self.GO_file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                if len(row) < 9:
                    print(f"⚠️ Skipped invalid GO row: {row}")
                    continue
                protein_id, ontology_id, validation, bp = row[1], row[4], row[6], row[8]
                if bp == "P" and validation != "IEA":
                    for ensembl_id in self.map__uniprotkb__ensembl_id.get(protein_id, []):
                        self.map__ensembl_id__gene_ontologies.setdefault(ensembl_id, set()).add((ontology_id, "GO"))

    def __load_reactome__(self):
        with open(self.Reactome_file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                if len(row) < 5:
                    print(f"⚠️ Skipped invalid Reactome row: {row}")
                    continue
                ensembl_id, ontology_id, validation = row[0], row[1], row[4]
                if "R-HSA" in ontology_id and "ENSG" in ensembl_id and validation != "IEA":
                    self.map__ensembl_id__gene_ontologies.setdefault(ensembl_id, set()).add((ontology_id, "Reactome"))

    def __load_KEGG__(self):
        with open(self.KEGG_file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                if len(row) < 2:
                    continue
                ontology_id, kegg_id = row[0], row[1]
                for uniprot_id in self.map__KEGG__uniprot_id.get(kegg_id, []):
                    for ensembl_id in self.map__uniprotkb__ensembl_id.get(uniprot_id, []):
                        self.map__ensembl_id__gene_ontologies.setdefault(ensembl_id, set()).add((ontology_id, "KEGG"))

    def __save_final_ontology__(self):
        with open(self.output_ontology_network_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow(["gene_id", "term_id", "DB"])
            for gene_id, records in self.map__ensembl_id__gene_ontologies.items():
                for term_id, db in records:
                    writer.writerow([gene_id, term_id, db])

    def run(self):
        print("🔍 Loading Uniprot to Ensembl mapping...")
        self.__load_uniprot_mapping__()
        print("🔍 Loading KEGG to Uniprot mapping...")
        self.__load_KEGG_to_uniprot_mapping__()
        print("🔍 Loading GO annotations...")
        self.__load_go__()
        print("🔍 Loading KEGG annotations...")
        self.__load_KEGG__()
        print("🔍 Loading Reactome annotations...")
        self.__load_reactome__()
        print("💾 Saving ontology network...")
        self.__save_final_ontology__()
        print(f"✅ Ontology network saved to {self.output_ontology_network_path}")
