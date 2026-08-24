"""Classifica vagas quanto a adequação, modalidade, cidade e nível.

Usa a API da Anthropic (Claude) quando ANTHROPIC_API_KEY está definida no
ambiente, para uma leitura mais robusta de descrições de vaga em formato
livre. Sem a chave, cai para uma heurística por palavras-chave — mais
simples, mas funcional offline e sem custo.
"""
from __future__ import annotations

import json
import logging
import os
import re

from textmatch import matching_keywords

log = logging.getLogger(__name__)

NIVEL_GERENTE = "Gerente (com gestão)"
NIVEL_ESPECIALISTA = "Especialista II (sem gestão)"
NIVEL_OUTRO = "Outro"

_GESTAO_KEYWORDS = [
    "gestão de equipe", "gestão de time", "liderança de equipe", "liderança de time",
    "gerenciar equipe", "gerenciar time", "people management", "team management",
    "liderar equipe", "liderar time", "supervisionar equipe", "gestão de pessoas",
]
_GERENTE_TITLE_KEYWORDS = ["gerente", "manager", "head de", "head of", "coordenador"]
_ESPECIALISTA_TITLE_KEYWORDS = ["especialista", "specialist", "senior", "sênior", "staff"]

_REMOTO_PATTERN = re.compile(r"\bremot|\bhome[\s-]?office\b|\bwork\s+from\s+home\b", re.IGNORECASE)
_HIBRIDO_PATTERN = re.compile(r"\bh[ií]brid", re.IGNORECASE)


def _heuristic_modalidade(text: str) -> str:
    if _REMOTO_PATTERN.search(text):
        return "remoto"
    if _HIBRIDO_PATTERN.search(text):
        return "híbrido"
    return "presencial"


def _heuristic_nivel(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    tem_gestao = any(kw in text for kw in _GESTAO_KEYWORDS)
    if tem_gestao or any(kw in title.lower() for kw in _GERENTE_TITLE_KEYWORDS):
        return NIVEL_GERENTE
    if any(kw in title.lower() for kw in _ESPECIALISTA_TITLE_KEYWORDS):
        return NIVEL_ESPECIALISTA
    return NIVEL_OUTRO


def _heuristic_adequacao(job: dict, profile: dict, preferences: dict) -> tuple[str, str, list[str]]:
    text = f"{job.get('title', '')} {job.get('description', '')}"

    keywords: set[str] = set()
    for group in profile.get("skills", {}).values():
        keywords.update(group)
    keywords.update(preferences.get("areas_e_palavras_chave", []))

    matched = sorted(set(matching_keywords(text, list(keywords))))
    score = len(matched)

    if score >= 5:
        adequacao = "Alta"
    elif score >= 2:
        adequacao = "Média"
    else:
        adequacao = "Baixa"

    justificativa = (
        f"{score} termo(s) do perfil encontrados na vaga: {', '.join(matched[:8])}."
        if matched else "Nenhum termo relevante do perfil encontrado na descrição da vaga."
    )
    return adequacao, justificativa, matched


def _heuristic_classify(job: dict, profile: dict, preferences: dict) -> dict:
    text = f"{job.get('title', '')} {job.get('description', '')}"
    adequacao, justificativa, matched = _heuristic_adequacao(job, profile, preferences)
    return {
        **job,
        "adequacao": adequacao,
        "adequacao_justificativa": justificativa,
        "termos_correspondentes": matched,
        "modalidade": _heuristic_modalidade(text),
        "cidade": job.get("location") or "não informado",
        "nivel": _heuristic_nivel(job.get("title", ""), job.get("description", "")),
        "classificado_por": "heuristica",
    }


_CLAUDE_SYSTEM_PROMPT = """\
Você ajuda a classificar vagas de emprego para um candidato específico.
Responda SOMENTE com um objeto JSON válido, sem texto adicional, com as chaves:
- "adequacao": "Alta", "Média" ou "Baixa"
- "adequacao_justificativa": string curta (1-2 frases) explicando o motivo
- "modalidade": "remoto", "híbrido", "presencial" ou "não informado"
- "cidade": string com a cidade da vaga (ou "não informado")
- "nivel": um destes três valores exatos: "Gerente (com gestão)", \
"Especialista II (sem gestão)" ou "Outro"
"""


def _claude_classify(job: dict, profile: dict, preferences: dict, client) -> dict:
    user_prompt = json.dumps({
        "vaga": {
            "titulo": job.get("title"),
            "empresa": job.get("company"),
            "localizacao": job.get("location"),
            "descricao": (job.get("description") or "")[:4000],
        },
        "perfil_candidato": {
            "resumo": profile.get("summary"),
            "niveis_alvo": profile.get("target_levels"),
            "skills": profile.get("skills"),
            "experiencia_mais_recente": profile.get("experiences", [{}])[0],
        },
        "preferencias": preferences,
    }, ensure_ascii=False)

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=700,
        system=_CLAUDE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw_text = "".join(block.text for block in response.content if hasattr(block, "text"))
    parsed = json.loads(raw_text)
    return {**job, **parsed, "classificado_por": "claude"}


DEFAULT_TOP_N_CLAUDE = 20


def classify_jobs(jobs: list[dict], profile: dict, preferences: dict) -> list[dict]:
    """Classifica todas as vagas com a heurística (grátis, instantânea) e depois
    refina apenas as N mais promissoras via Claude (mais preciso, porém mais
    lento e pago). N vem de preferences["vagas_para_refinar_com_claude"],
    com default DEFAULT_TOP_N_CLAUDE.

    Isso evita chamar a API uma vez por vaga — com centenas de vagas por dia,
    classificar tudo via LLM fica caro e lento pra pouco ganho, já que a
    maioria nem chega perto do perfil.
    """
    heuristic_results = [_heuristic_classify(job, profile, preferences) for job in jobs]

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return heuristic_results

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except ImportError:
        log.warning("Pacote 'anthropic' não instalado — usando heurística para todas as vagas.")
        return heuristic_results

    top_n = preferences.get("vagas_para_refinar_com_claude", DEFAULT_TOP_N_CLAUDE)
    ranked = sorted(heuristic_results, key=lambda j: len(j.get("termos_correspondentes", [])), reverse=True)
    top_ids = {job["id"] for job in ranked[:top_n]}
    log.info(
        "Refinando as %d vagas mais promissoras via Claude (de %d no total, pela heurística).",
        len(top_ids), len(heuristic_results),
    )

    refined = []
    for job in heuristic_results:
        if job["id"] in top_ids:
            try:
                refined.append(_claude_classify(job, profile, preferences, client))
                continue
            except Exception as exc:  # noqa: BLE001 - fallback deliberado
                log.warning("Falha ao refinar '%s' via Claude (%s); mantendo heurística.", job.get("title"), exc)
        refined.append(job)

    return refined
