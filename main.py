"""Orquestrador do fluxo diário do agente de recolocação.

Uso:
    python main.py               # roda o fluxo completo (busca, classificação,
                                  # upload no Drive e envio de e-mail)
    python main.py --dry-run     # roda busca + classificação e salva os
                                  # resultados localmente, sem subir no Drive
                                  # nem enviar e-mail (use isso primeiro)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

load_dotenv(PROJECT_ROOT / ".env")

import ssl_fix  # noqa: E402,F401 - precisa rodar antes de qualquer chamada de rede
import search_adzuna  # noqa: E402
import classify  # noqa: E402
import summarize  # noqa: E402

log = logging.getLogger("main")

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
DESKTOP_RESULTS_DIR = PROJECT_ROOT.parent / "Vagas"


def setup_logging(run_date_str: str) -> None:
    log_dir = OUTPUT_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / f"{run_date_str}.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run(dry_run: bool) -> None:
    run_date = date.today()
    run_date_str = run_date.isoformat()
    setup_logging(run_date_str)

    log.info("=== Execução diária do agente de recolocação — %s (dry_run=%s) ===", run_date_str, dry_run)

    profile = load_json(DATA_DIR / "profile.json")
    preferences = load_json(DATA_DIR / "preferences.json")

    log.info("Buscando vagas...")
    jobs = search_adzuna.search_jobs(preferences)
    log.info("%d vagas encontradas antes da classificação.", len(jobs))

    log.info("Classificando vagas...")
    classified = classify.classify_jobs(jobs, profile, preferences)

    n_alta = sum(1 for j in classified if j.get("adequacao") == "Alta")
    log.info("Classificação concluída: %d vagas, %d de alta adequação.", len(classified), n_alta)

    markdown_summary = summarize.build_executive_summary_markdown(classified, run_date)
    csv_content = summarize.jobs_to_csv(classified)

    results_dir = OUTPUT_DIR / "runs" / run_date_str
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "resumo.md").write_text(markdown_summary, encoding="utf-8")
    (results_dir / "vagas.csv").write_text(csv_content, encoding="utf-8")
    log.info("Resultados salvos localmente em %s", results_dir)

    desktop_dir = DESKTOP_RESULTS_DIR / run_date_str
    desktop_dir.mkdir(parents=True, exist_ok=True)
    (desktop_dir / "resumo.md").write_text(markdown_summary, encoding="utf-8")
    (desktop_dir / "vagas.csv").write_text(csv_content, encoding="utf-8")
    log.info("Cópia dos resultados também salva em %s", desktop_dir)

    if dry_run:
        log.info("dry-run: pulando upload no Drive e envio de e-mail.")
        print(markdown_summary)
        return

    sheet_link = None
    try:
        import drive

        links = drive.upload_daily_results(markdown_summary, csv_content, run_date_str)
        sheet_link = links.get("planilha")
        log.info("Upload no Drive concluído: %s", links)
    except Exception as exc:  # noqa: BLE001
        log.error("Falha ao subir resultados para o Drive: %s", exc)

    try:
        import mailer

        email_html = summarize.build_executive_summary_html(classified, run_date, sheet_link=sheet_link)
        subject = f"[Recolocação] {n_alta} vaga(s) de alta adequação — {run_date.strftime('%d/%m/%Y')}"
        if sheet_link:
            # A lista completa já está linkada (Google Sheets) — sem anexo.
            mailer.send_daily_summary(subject, email_html)
        else:
            # Drive falhou: anexa o CSV pra não perder a lista completa.
            mailer.send_daily_summary(subject, email_html, csv_content, f"vagas-{run_date_str}.csv")
    except Exception as exc:  # noqa: BLE001
        log.error("Falha ao enviar e-mail: %s", exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fluxo diário do agente de recolocação.")
    parser.add_argument("--dry-run", action="store_true", help="Não sobe no Drive nem envia e-mail.")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
