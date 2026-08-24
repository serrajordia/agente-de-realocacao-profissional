# Setup — passo a passo

Python 3.12 e Typst já foram instalados nesta máquina (via winget). Falta
completar os passos abaixo, que são pessoais e não podem ser feitos por mim.

## 1. Instalar as dependências Python

```bash
cd "C:\Users\juka\OneDrive\Desktop\recolocacao-agent"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Criar o arquivo .env

Copie `.env.example` para `.env` e preencha conforme os passos abaixo.

## 3. Adzuna (busca de vagas) — obrigatório

1. Crie uma conta gratuita em https://developer.adzuna.com/
2. Copie o `app_id` e o `app_key` gerados.
3. Preencha `ADZUNA_APP_ID` e `ADZUNA_APP_KEY` no `.env`.

## 4. Gmail — senha de app (obrigatório para enviar o e-mail diário)

1. Em myaccount.google.com, ative a **Verificação em duas etapas** (se ainda
   não estiver ativa).
2. Acesse https://myaccount.google.com/apppasswords
3. Gere uma senha de app para "Mail" / "Outro (nome personalizado)" — ex:
   "Agente Recolocação".
4. Copie a senha de 16 caracteres gerada e preencha `SMTP_PASSWORD` no
   `.env` (o `SMTP_USER` já deve ser juka42@gmail.com).

## 5. Google Drive — credenciais OAuth (obrigatório para o upload automático)

1. Acesse https://console.cloud.google.com/ e crie um projeto novo (ou use
   um existente).
2. No menu "APIs e serviços" → "Biblioteca", habilite a **Google Drive API**.
3. Em "APIs e serviços" → **"Google Auth Platform"** (nome novo do que era
   "Tela de consentimento OAuth"; só aparece depois de habilitar uma API):
   - Aba **Branding**: nome do app e e-mail de suporte.
   - Aba **Audience**: escolha **"External"**; em "Test users" clique
     "Add users" e adicione juka42@gmail.com — isso evita ter que publicar
     o app publicamente.
   - Aba **Data Access**: pode deixar como está.
4. Ainda no Google Auth Platform, aba **Clients** → "Create Client" → tipo
   de aplicativo **"Desktop app"** (equivalente ao antigo "App para
   computador" em Credenciais).
5. Baixe o JSON gerado e salve como `credentials.json` na raiz do projeto
   (`C:\Users\juka\OneDrive\Desktop\recolocacao-agent\credentials.json`).
6. Na primeira execução (`python main.py --dry-run` não aciona o Drive; use
   `python main.py` sem `--dry-run` ou rode `python -c "import sys;
   sys.path.insert(0,'src'); import drive;
   drive.upload_daily_results('teste','a,b\n1,2','teste')"` a partir da
   pasta do projeto) uma janela do navegador vai abrir pedindo para você
   logar e autorizar o acesso. Depois disso, um `token.json` é salvo e
   reaproveitado nas próximas execuções (renovado automaticamente).

## 6. (Opcional) Claude API — classificação e CV mais inteligentes

Sem isso, o agente funciona com uma heurística por palavras-chave (mais
simples, mas sem custo). Com uma `ANTHROPIC_API_KEY` preenchida no `.env`,
a classificação de vagas e a geração do resumo/CV ficam mais precisas.

1. Gere uma chave em https://console.anthropic.com/
2. Preencha `ANTHROPIC_API_KEY` no `.env`.

## 7. Testar antes de confiar no agendamento

```bash
python main.py --dry-run
```

Isso busca e classifica as vagas e salva os resultados em
`output/runs/<data>/`, sem subir no Drive nem enviar e-mail. Confira o
`resumo.md` gerado.

Quando estiver satisfeito, rode uma vez sem `--dry-run` para validar o
e-mail e o upload no Drive:

```bash
python main.py
```

## 8. Agendar a execução diária

Veja a seção "Agendamento" do README.md — o script
`schedule_task.ps1` cria a tarefa no Windows Task Scheduler automaticamente.
