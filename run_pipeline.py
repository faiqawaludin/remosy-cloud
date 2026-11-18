import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DBT_DIR = BASE_DIR / "dbt_remosy"
PYTHON_EXEC = sys.executable
DBT_EXEC = shutil.which("dbt") or str(Path(PYTHON_EXEC).parent / "dbt.exe")


def run_step(title: str, command: list[str], cwd: Path = BASE_DIR):
    print(f"\n{'=' * 60}\n[STEP] {title}\n{'=' * 60}", flush=True)
    result = subprocess.run(command, cwd=cwd)
    if result.returncode != 0:
        print(f"\n[ERROR] Pipeline berhenti pada tahap: {title}", flush=True)
        sys.exit(result.returncode)


if __name__ == "__main__":
    # 1. Extract & Load ke Bronze
    run_step(
        "1. Extract & Load Google News -> Bronze",
        [PYTHON_EXEC, "src/extract/extract_news.py"],
    )
    run_step(
        "1b. Extract & Load X/Twitter -> Bronze", [sys.executable, "extract_twitter.py"]
    )

    # 2. Transformasi Pembersihan & Deduplikasi ke Silver
    run_step(
        "2. dbt Silver Transformation (stg_news)",
        [DBT_EXEC, "run", "--select", "silver"],
        cwd=DBT_DIR,
    )

    # 3. Pelabelan Sentimen IndoBERT + Hybrid Logic ke Silver
    run_step(
        "3. IndoBERT Sentiment Inference -> Silver",
        [PYTHON_EXEC, "src/ml/predict_sentiment.py"],
    )

    # 4. Bangun Star Schema & Marts di Gold + Data Quality Tests
    run_step(
        "4. dbt Gold Star Schema & Marts",
        [DBT_EXEC, "run", "--select", "gold"],
        cwd=DBT_DIR,
    )
    run_step(
        "5. dbt Gold Data Quality Tests",
        [DBT_EXEC, "test", "--select", "gold"],
        cwd=DBT_DIR,
    )

    print("\n[SUCCESS] Seluruh pipeline ELT REMOSY selesai dijalankan!")
