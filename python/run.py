import os
import sys
import subprocess
import time

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.join(ROOT_DIR, "pipeline")

PIPELINES = [
    ("Step 1 - PP-OCRv6 OCR", "step1_ppocrv6_ocr.py"),
    ("Step 2 - Layout + Style + Image/Logo Analysis", "step2_layout_analysis.py"),
    ("Step 3 - Reading Order", "step3_reading_order.py"),
    ("Step 4 - DOCX Builder", "step4_docx_builder.py"),
]


def run_step(title, script):
    print("=" * 70)
    print(title)
    print("=" * 70)

    start = time.time()

    path = os.path.join(PIPELINE_DIR, script)

    result = subprocess.run(
        [sys.executable, path],
        cwd=PIPELINE_DIR
    )

    if result.returncode != 0:
        print(f"FAILED: {title}")
        sys.exit(result.returncode)

    print(f"Done: {time.time() - start:.2f}s\n")


def main():
    start = time.time()

    for title, script in PIPELINES:
        run_step(title, script)

    print("=" * 70)
    print("PIPELINE COMPLETED")
    print("=" * 70)
    print(f"Total: {time.time() - start:.2f}s")


if __name__ == "__main__":
    main()