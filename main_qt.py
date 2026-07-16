import argparse

from biorank_qt.app import run_optimizer_app


def main():
    parser = argparse.ArgumentParser(description="Launch the BioRank Qt optimizer.")
    parser.add_argument("--disease", default="BRCA", help="Initial TCGA disease code.")
    args = parser.parse_args()
    return run_optimizer_app(selected_disease=args.disease)


if __name__ == "__main__":
    raise SystemExit(main())
