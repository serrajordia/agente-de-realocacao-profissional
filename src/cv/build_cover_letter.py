"""Gera uma carta de apresentação (cover letter) em PDF customizada para uma vaga.

Uso:
    python src/cv/build_cover_letter.py --job-file caminho.txt --empresa "Bunge" --cargo "Data Scientist Manager"
    python src/cv/build_cover_letter.py --job-text "texto da vaga..." --empresa "Bunge" --cargo "Data Scientist Manager"

Requer ANTHROPIC_API_KEY — diferente do CV, uma carta de apresentação é texto
persuasivo customizado; sem um LLM por trás, o resultado não vale a pena.
Reaproveita a cor de marca (COMPANY_ACCENT_COLORS) e a estrutura de pastas do
build_cv.py, para o CV e a carta saírem visualmente combinando.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_cv import (  # noqa: E402
    DESKTOP_CV_DIR,
    OUTPUT_ROOT,
    PROFILE_PATH,
    resolve_accent_color,
    slugify,
)

log = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).resolve().parent / "cover_letter_template.typ"

_MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def data_por_extenso(d: date, cidade: str = "São Paulo") -> str:
    return f"{cidade}, {d.day} de {_MESES[d.month - 1]} de {d.year}"


def build_paragraphs(profile: dict, job_text: str, empresa: str) -> list[str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY não configurada. Uma carta de apresentação é texto "
            "persuasivo customizado — sem o Claude por trás não vale a pena gerar "
            "(o CV funciona sem a chave, a carta não)."
        )

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    profile_context = {
        "resumo": profile.get("summary"),
        "experiencias": profile.get("experiences"),
        "projetos": profile.get("projects"),
        "skills": profile.get("skills"),
    }

    prompt = (
        f"Escreva uma carta de apresentação (cover letter) em português do Brasil, "
        f"profissional mas com voz própria (não genérica nem robótica), para a vaga "
        f"abaixo na empresa {empresa}. Baseie-se SOMENTE nos fatos do perfil "
        f"fornecido — não invente experiências, números ou realizações que não "
        f"estejam lá.\n\n"
        f"Estrutura: 3 a 4 parágrafos corridos, SEM saudação nem despedida (isso é "
        f"adicionado separadamente). Primeiro parágrafo: interesse na vaga e um "
        f"gancho rápido e específico. Parágrafo(s) do meio: conecte experiências e "
        f"realizações concretas do perfil aos requisitos da vaga, com exemplos "
        f"reais. Último parágrafo: reforce o fit e feche com disposição para "
        f"conversar.\n\n"
        f"Responda APENAS com os parágrafos, cada um separado por uma linha em "
        f"branco, sem títulos, marcadores, saudação, despedida ou comentários.\n\n"
        f"PERFIL:\n{json.dumps(profile_context, ensure_ascii=False)}\n\n"
        f"VAGA (empresa: {empresa}):\n{job_text[:6000]}"
    )

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if hasattr(block, "text")).strip()
    if response.stop_reason == "max_tokens":
        raise RuntimeError("A carta foi cortada por limite de tokens da resposta — tente novamente.")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        raise RuntimeError("Claude retornou uma carta vazia — tente novamente.")
    return paragraphs


def compile_letter(tailored_data: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(TEMPLATE_PATH, out_dir / "cover_letter_template.typ")
    (out_dir / "cover_letter_data.json").write_text(
        json.dumps(tailored_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    pdf_path = out_dir / "carta_apresentacao.pdf"
    result = subprocess.run(
        ["typst", "compile", "cover_letter_template.typ", "carta_apresentacao.pdf"],
        cwd=out_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Falha ao compilar a carta com Typst:\n{result.stderr}")
    return pdf_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera uma carta de apresentação em PDF para uma vaga.")
    parser.add_argument("--job-file", type=Path, help="Arquivo texto com a descrição da vaga.")
    parser.add_argument("--job-text", type=str, help="Texto da descrição da vaga (alternativa a --job-file).")
    parser.add_argument("--empresa", type=str, required=True, help="Nome da empresa.")
    parser.add_argument("--cargo", type=str, default="vaga", help="Nome do cargo (usado no nome da pasta).")
    parser.add_argument("--cor", type=str, default=None, help="Cor de destaque em hex, sobrepõe a cor cadastrada para a empresa.")
    args = parser.parse_args()

    if not args.job_file and not args.job_text:
        parser.error("Informe --job-file ou --job-text.")

    job_text = args.job_file.read_text(encoding="utf-8") if args.job_file else args.job_text
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))

    paragraphs = build_paragraphs(profile, job_text, args.empresa)
    accent_color = resolve_accent_color(args.empresa, args.cor)

    tailored = {
        "personal": profile["personal"],
        "accent_color": accent_color,
        "data_extenso": data_por_extenso(date.today()),
        "saudacao": f"Prezados(as) recrutadores(as) da {args.empresa},",
        "paragrafos": paragraphs,
        "despedida": "Atenciosamente,",
    }

    slug = f"{slugify(args.empresa)}_{slugify(args.cargo)}"
    out_dir = OUTPUT_ROOT / slug
    pdf_path = compile_letter(tailored, out_dir)

    desktop_dir = DESKTOP_CV_DIR / slug
    shutil.copytree(out_dir, desktop_dir, dirs_exist_ok=True)

    print(f"Carta gerada em: {pdf_path}")
    print(f"Cópia salva em: {desktop_dir}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
