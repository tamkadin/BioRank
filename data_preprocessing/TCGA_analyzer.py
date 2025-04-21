import os
import csv
import gzip

class TCGAAnalyzer:
    def __init__(self, sample_sheet_file_path, manifest_file_path, TCGA_directory_path, output_dir_path):
        self.sample_sheet_file_path = sample_sheet_file_path
        self.manifest_file_path = manifest_file_path
        self.TCGA_directory_path = TCGA_directory_path
        self.output_dir_path = output_dir_path

    def __load_manifest_files__(self):
        self.manifest_sample_ids = set()
        with open(self.manifest_file_path, "r") as f:
            reader = csv.reader(f, delimiter="\t")
            for row in reader:
                self.manifest_sample_ids.add(row[0])  # ID cột đầu tiên trong manifest

    def __create_mapping_tumor_sane_samples__(self):
        self.TCGA_map__project_id___dictionary = {}

        with open(self.sample_sheet_file_path, "r") as f:
            reader = csv.reader(f, delimiter="\t")
            for index, row in enumerate(reader):
                if index == 0:
                    continue  # Bỏ header

                file_id, file_name, project_id = row[0], row[1], row[4]
                sample_id = row[6]
                type_code = sample_id.split("-")[-1][:2]  # Lấy mã phân biệt tumor/control

                if project_id not in self.TCGA_map__project_id___dictionary:
                    self.TCGA_map__project_id___dictionary[project_id] = {"T": {}, "C": {}}

                # T: tumor (01), C: control (11)
                if type_code == "01":
                    self.TCGA_map__project_id___dictionary[project_id]["T"][file_id] = (file_name, file_id)
                elif type_code == "11":
                    self.TCGA_map__project_id___dictionary[project_id]["C"][file_id] = (file_name, file_id)

    def __get_map__patient__ensembl_id__expression(self, case_control_dict):
        patient_set, gene_set = set(), set()
        map__patient__ensembl_id__expression = {}

        for file_id, (file_name, case_id) in case_control_dict.items():
            file_path = os.path.join(self.TCGA_directory_path, file_id, file_name)
            map__patient__ensembl_id__expression[case_id] = {}
            patient_set.add(case_id)

            try:
                with gzip.open(file_path, mode='rt') as f:  # ✅ sửa tại đây: đọc file ở dạng văn bản
                    reader = csv.reader(f, delimiter="\t")
                    for row in reader:
                        if not row or len(row) < 2:
                            continue
                        ensembl_id, rna = row[0], row[1]
                        gene_set.add(ensembl_id)
                        map__patient__ensembl_id__expression[case_id][ensembl_id] = rna
            except Exception as e:
                print(f"❌ Error reading {file_path}: {e}")

        return patient_set, gene_set, map__patient__ensembl_id__expression

    def __write_table__(self, patient_set, gene_set, expression_map, project_id, label):
        output_file = os.path.join(self.output_dir_path, f"{project_id}__{label}.tsv")

        with open(output_file, "w", newline="") as f:
            writer = csv.writer(f, delimiter="\t")
            gene_list = sorted(gene_set)
            patient_list = sorted(patient_set)

            writer.writerow(["Gene_ID"] + patient_list)
            for gene in gene_list:
                row = [gene] + [expression_map.get(patient, {}).get(gene, "0") for patient in patient_list]
                writer.writerow(row)

    def create_tumor_control_table(self):
        self.__load_manifest_files__()
        self.__create_mapping_tumor_sane_samples__()

        for project_id, case_control_dict in self.TCGA_map__project_id___dictionary.items():
            print(f"🧬 Processing project: {project_id}")

            tumor_set, tumor_genes, tumor_expr = self.__get_map__patient__ensembl_id__expression(case_control_dict["T"])
            control_set, control_genes, control_expr = self.__get_map__patient__ensembl_id__expression(case_control_dict["C"])

            self.__write_table__(tumor_set, tumor_genes, tumor_expr, project_id, "tumor")
            self.__write_table__(control_set, control_genes, control_expr, project_id, "control")

        print(f"✅ All tumor/control tables written to: {self.output_dir_path}")
