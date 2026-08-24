"""Gera um CV em PDF (via Typst) customizado para uma vaga específica.

Uso:
    python src/cv/build_cv.py --job-file caminho/para/descricao.txt --empresa "Empresa X" --cargo "Gerente de Risco"
    python src/cv/build_cv.py --job-text "texto da vaga aqui..." --empresa "Empresa X" --cargo "Gerente de Risco"

Lê data/profile.json, seleciona/prioriza experiências e skills mais
relevantes para a vaga (via Claude, se ANTHROPIC_API_KEY estiver definida;
senão por interseção de palavras-chave), grava tailored_data.json e chama
`typst compile` para gerar o PDF em output/cv/<slug>/cv.pdf.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ssl_fix  # noqa: E402,F401 - precisa rodar antes de qualquer chamada de rede
from textmatch import contains_keyword, matching_keywords  # noqa: E402

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

PROFILE_PATH = PROJECT_ROOT / "data" / "profile.json"
TEMPLATE_PATH = Path(__file__).resolve().parent / "template.typ"
OUTPUT_ROOT = PROJECT_ROOT / "output" / "cv"
DESKTOP_CV_DIR = PROJECT_ROOT.parent / "Vagas" / "CVs"

MAX_EXPERIENCES = 6
MAX_BULLETS_PER_EXPERIENCE = 4
MAX_SKILLS = 18

DEFAULT_ACCENT_COLOR = "#1F2937"  # cinza-azulado neutro, usado quando a empresa não está no dicionário

# Cores de marca verificadas (não chutar — cor errada é pior que não ter cor).
# Adicione mais entradas conforme for gerando CVs para novas empresas.
COMPANY_ACCENT_COLORS = {
    "bunge": "#002D6E",
}


def resolve_accent_color(empresa: str, override: str | None) -> str:
    if override:
        return override if override.startswith("#") else f"#{override}"
    key = unicodedata.normalize("NFKD", empresa).encode("ascii", "ignore").decode("ascii").strip().lower()
    return COMPANY_ACCENT_COLORS.get(key, DEFAULT_ACCENT_COLOR)


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s_-]+", "-", text) or "vaga"


def _score(text: str, keywords: list[str]) -> int:
    return len(matching_keywords(text, keywords))


def _experience_score(job_text: str, exp: dict) -> int:
    bullets_text = " ".join(exp.get("bullets", []))
    keywords = (
        exp.get("skills_used", [])
        + _significant_words(exp.get("role", ""), limit=None)
        + _significant_words(bullets_text, limit=None)
    )
    return _score(job_text, keywords)


def select_experiences(profile: dict, job_text: str) -> list[dict]:
    experiences = profile.get("experiences", [])
    scored = [(exp, _experience_score(job_text, exp)) for exp in experiences]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    top = [exp for exp, _ in scored[:MAX_EXPERIENCES]]

    top_ids = {id(exp) for exp in top}
    ordered = [exp for exp in experiences if id(exp) in top_ids]

    trimmed = []
    for exp in ordered:
        bullets = exp.get("bullets", [])
        bullet_scores = [(b, _score(job_text, exp.get("skills_used", []) + _significant_words(b))) for b in bullets]
        bullet_scores.sort(key=lambda pair: pair[1], reverse=True)
        top_bullets = [b for b, _ in bullet_scores[:MAX_BULLETS_PER_EXPERIENCE]] or bullets[:MAX_BULLETS_PER_EXPERIENCE]
        trimmed.append({**exp, "bullets": top_bullets})
    return trimmed


_STOPWORDS = {
    "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas", "para", "por",
    "com", "sem", "que", "uma", "um", "uns", "umas", "os", "as", "ao", "aos", "às",
    "e", "ou", "a", "o", "the", "of", "and", "for", "to", "in", "on",
}


def _significant_words(text: str, limit: int | None = 6) -> list[str]:
    words = [w for w in re.findall(r"\w+", text) if len(w) > 3 and w.lower() not in _STOPWORDS]
    return words[:limit]


def select_skills(profile: dict, job_text: str) -> list[str]:
    all_skills: list[str] = []
    for group in profile.get("skills", {}).values():
        all_skills.extend(group)

    matched = [s for s in all_skills if contains_keyword(job_text, s)]
    rest = [s for s in all_skills if s not in matched]
    ordered = matched + rest
    seen = set()
    unique = []
    for s in ordered:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique[:MAX_SKILLS]


def build_summary(profile: dict, job_text: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key or not job_text.strip():
        return profile.get("summary", "")

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            "Reescreva o resumo profissional abaixo em português, mantendo os fatos "
            "(não invente experiência nova), com 3 a 4 frases, destacando os pontos "
            "mais relevantes para a vaga descrita a seguir. Responda apenas com o "
            "texto do resumo, sem aspas ou comentários.\n\n"
            f"RESUMO ATUAL:\n{profile.get('summary', '')}\n\n"
            f"VAGA:\n{job_text[:3000]}"
        )
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if hasattr(block, "text")).strip()
        return text or profile.get("summary", "")
    except Exception as exc:  # noqa: BLE001 - fallback deliberado
        log.warning("Falha ao gerar resumo customizado via Claude (%s); usando resumo padrão.", exc)
        return profile.get("summary", "")


def build_tailored_data(profile: dict, job_text: str, accent_color: str = DEFAULT_ACCENT_COLOR) -> dict:
    return {
        "personal": profile["personal"],
        "accent_color": accent_color,
        "summary": build_summary(profile, job_text),
        "skills_flat": select_skills(profile, job_text),
        "experiences": select_experiences(profile, job_text),
        "education": profile.get("education", []),
        "languages_flat": [f"{l['language']}: {l['level']}" for l in profile.get("languages", [])],
        "certifications_flat": [
            f"{c['name']}" + (f" — {c['issuer']}" if c.get("issuer") and c["issuer"] != "n/d" else "")
            + (f" ({c['year']})" if c.get("year") else "")
            for c in profile.get("certifications", [])
        ],
    }


def compile_cv(tailored_data: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(TEMPLATE_PATH, out_dir / "template.typ")
    (out_dir / "tailored_data.json").write_text(
        json.dumps(tailored_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    pdf_path = out_dir / "cv.pdf"
    result = subprocess.run(
        ["typst", "compile", "template.typ", "cv.pdf"],
        cwd=out_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Falha ao compilar o CV com Typst:\n{result.stderr}")
    return pdf_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera um CV customizado para uma vaga específica.")
    parser.add_argument("--job-file", type=Path, help="Arquivo texto com a descrição da vaga.")
    parser.add_argument("--job-text", type=str, help="Texto da descrição da vaga (alternativa a --job-file).")
    parser.add_argument("--geral", action="store_true", help="Gera um CV geral, sem vaga específica (usa as experiências mais recentes, sem priorização).")
    parser.add_argument("--empresa", type=str, default="empresa", help="Nome da empresa (usado no nome da pasta e para escolher a cor de destaque).")
    parser.add_argument("--cargo", type=str, default="vaga", help="Nome do cargo (usado no nome da pasta).")
    parser.add_argument("--cor", type=str, default=None, help="Cor de destaque em hex (ex: '#002D6E'), sobrepõe a cor cadastrada para a empresa.")
    args = parser.parse_args()

    if not args.geral and not args.job_file and not args.job_text:
        parser.error("Informe --job-file, --job-text ou --geral.")

    if args.geral:
        job_text = ""
    else:
        job_text = args.job_file.read_text(encoding="utf-8") if args.job_file else args.job_text
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))

    accent_color = resolve_accent_color(args.empresa, args.cor)
    tailored = build_tailored_data(profile, job_text, accent_color)
    slug = f"{slugify(args.empresa)}_{slugify(args.cargo)}"
    out_dir = OUTPUT_ROOT / slug
    pdf_path = compile_cv(tailored, out_dir)

    desktop_dir = DESKTOP_CV_DIR / slug
    shutil.copytree(out_dir, desktop_dir, dirs_exist_ok=True)

    print(f"CV gerado em: {pdf_path}")
    print(f"Cópia (com fonte .typ e dados) salva em: {desktop_dir}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
