"""Upload dos resultados diários para o Google Drive.

Usa OAuth próprio do script (não depende do Claude Code estar aberto).
Na primeira execução abre o navegador para consentimento único; depois
disso reutiliza `token.json` (renovado automaticamente).

Setup necessário: ver SETUP.md — criar um OAuth Client ID tipo "Desktop app"
no Google Cloud Console, habilitar a Google Drive API, e salvar o JSON
baixado como `credentials.json` na raiz do projeto.
"""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path

import ssl_fix  # noqa: F401 - precisa rodar antes de qualquer chamada de rede

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = Path(os.environ.get("GOOGLE_DRIVE_CREDENTIALS_FILE", PROJECT_ROOT / "credentials.json"))
TOKEN_FILE = Path(os.environ.get("GOOGLE_DRIVE_TOKEN_FILE", PROJECT_ROOT / "token.json"))
ROOT_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "1jzbBVlf7bao2WYPcstp5ahVkrdiSIvDv")


def _get_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"'{CREDENTIALS_FILE}' não encontrado. Siga o SETUP.md para gerar as "
                    "credenciais OAuth do Google Drive antes de usar o upload."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return creds


def _get_service():
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=_get_credentials())


def _create_folder(service, name: str, parent_id: str) -> str:
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def upload_text_file(
    service, name: str, content: str, mime_type: str, parent_id: str, target_mime_type: str | None = None
) -> str:
    from googleapiclient.http import MediaIoBaseUpload

    media = MediaIoBaseUpload(io.BytesIO(content.encode("utf-8")), mimetype=mime_type)
    metadata = {"name": name, "parents": [parent_id]}
    if target_mime_type:
        metadata["mimeType"] = target_mime_type
    uploaded = service.files().create(body=metadata, media_body=media, fields="id, webViewLink").execute()
    return uploaded.get("webViewLink", uploaded.get("id"))


def upload_binary_file(
    service, name: str, content: bytes, mime_type: str, parent_id: str, target_mime_type: str | None = None
) -> str:
    from googleapiclient.http import MediaIoBaseUpload

    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type)
    metadata = {"name": name, "parents": [parent_id]}
    if target_mime_type:
        metadata["mimeType"] = target_mime_type
    uploaded = service.files().create(body=metadata, media_body=media, fields="id, webViewLink").execute()
    return uploaded.get("webViewLink", uploaded.get("id"))


def upload_daily_results(markdown_summary: str, xlsx_content: bytes, run_date_str: str) -> dict:
    """Cria a subpasta Vagas/<data> e sobe o resumo (md) e a lista completa.

    A lista completa sobe como uma planilha Google Sheets nativa (não um
    arquivo .xlsx) — a API do Drive converte automaticamente o XLSX enviado
    quando o mimeType de destino é de planilha. Isso permite editar a coluna
    "feedback" direto no navegador, sem precisar baixar nada.

    Retorna dict com os links dos arquivos criados. Se as credenciais não
    estiverem configuradas, levanta FileNotFoundError (o chamador decide
    se trata isso como fatal ou apenas loga um aviso).
    """
    service = _get_service()

    vagas_folder_id = _find_or_create_subfolder(service, "Vagas", ROOT_FOLDER_ID)
    day_folder_id = _create_folder(service, run_date_str, vagas_folder_id)

    resumo_link = upload_text_file(
        service, f"resumo-{run_date_str}.md", markdown_summary, "text/markdown", day_folder_id
    )
    planilha_link = upload_binary_file(
        service, f"vagas-{run_date_str}", xlsx_content,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", day_folder_id,
        target_mime_type="application/vnd.google-apps.spreadsheet",
    )

    log.info("Upload para o Drive concluído: %s", day_folder_id)
    return {"resumo": resumo_link, "planilha": planilha_link, "folder_id": day_folder_id}


def _find_or_create_subfolder(service, name: str, parent_id: str) -> str:
    query = (
        f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents and trashed = false"
    )
    try:
        results = service.files().list(q=query, fields="files(id)", pageSize=1).execute()
        files = results.get("files", [])
        if files:
            return files[0]["id"]
    except Exception as exc:  # noqa: BLE001
        log.warning("Busca da subpasta '%s' falhou (%s); criando uma nova.", name, exc)
    return _create_folder(service, name, parent_id)
