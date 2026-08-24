"""Busca vagas usando a Adzuna Job Search API (https://developer.adzuna.com/).

Requer ADZUNA_APP_ID e ADZUNA_APP_KEY no ambiente (.env). Sem essas
variáveis, retorna uma lista vazia (o restante do pipeline continua
funcionando com as outras fontes).
"""
from __future__ import annotations

import logging
import os
import time

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
# Mantido enxuto de propósito: muitas requisições seguidas (mesmo que dentro
# do limite diário da Adzuna) podem disparar rate-limiting por IP no lado
# deles, o que pode atrapalhar você navegando/candidatando-se no site deles
# na mesma rede logo em seguida.
MAX_KEYWORDS = 6
MAX_PAGES_PER_KEYWORD = 1
RESULTS_PER_PAGE = 50
REQUEST_DELAY_SECONDS = 2.0


def _normalize(job: dict) -> dict:
    return {
        "source": "adzuna",
        "id": f"adzuna:{job.get('id')}",
        "title": job.get("title", "").strip(),
        "company": (job.get("company") or {}).get("display_name", "").strip(),
        "location": (job.get("location") or {}).get("display_name", "").strip(),
        "description": job.get("description", "").strip(),
        "url": job.get("redirect_url", ""),
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "contract_type": job.get("contract_time") or job.get("contract_type"),
        "category": (job.get("category") or {}).get("label"),
        "created": job.get("created"),
    }


def search_jobs(preferences: dict, country: str = "br") -> list[dict]:
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        log.warning("ADZUNA_APP_ID/ADZUNA_APP_KEY não configurados — pulando busca no Adzuna.")
        return []

    keywords = preferences.get("areas_e_palavras_chave", [])[:MAX_KEYWORDS]
    seen_ids: set[str] = set()
    results: list[dict] = []

    for keyword in keywords:
        for page in range(1, MAX_PAGES_PER_KEYWORD + 1):
            url = BASE_URL.format(country=country, page=page)
            params = {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": RESULTS_PER_PAGE,
                "what": keyword,
                "content-type": "application/json",
            }
            try:
                resp = requests.get(url, params=params, timeout=20)
                resp.raise_for_status()
            except requests.RequestException as exc:
                log.warning("Falha ao buscar '%s' (página %s) no Adzuna: %s", keyword, page, exc)
                break

            payload = resp.json()
            jobs = payload.get("results", [])
            if not jobs:
                break

            for raw_job in jobs:
                job = _normalize(raw_job)
                if job["id"] not in seen_ids:
                    seen_ids.add(job["id"])
                    results.append(job)

            time.sleep(REQUEST_DELAY_SECONDS)

    log.info("Adzuna: %d vagas únicas encontradas para %d palavras-chave.", len(results), len(keywords))
    return results
