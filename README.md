# Agente de Recolocação

Agente local (Python) que roda toda manhã para apoiar a busca de recolocação
no mercado: pesquisa vagas, classifica adequação/modalidade/cidade/nível,
monta um resumo executivo, envia por e-mail e sobe os resultados no Google
Drive. Também gera versões do CV e da carta de apresentação em PDF (via
Typst) customizadas para uma vaga específica, a partir de um banco de dados
único em `data/profile.json`.

Feito para uso pessoal com [Claude Code](https://claude.com/claude-code) e
compartilhado como ponto de partida — os dados de exemplo em
`data/profile.example.json` são reais (do autor, que autorizou publicá-los;
é essencialmente o mesmo conteúdo já público no LinkedIn dele), pra você ver
o formato esperado. Seus próprios dados ficam em arquivos separados,
ignorados pelo Git (veja abaixo).

## Primeiro uso

1. Copie os arquivos de exemplo para os arquivos reais que o agente lê:
   ```bash
   cp data/profile.example.json data/profile.json
   cp data/preferences.example.json data/preferences.json
   ```
   Edite os dois com as suas informações — `profile.json` é o banco de dados
   único (experiências, skills, projetos, idiomas) e `preferences.json` são
   os critérios de busca (níveis-alvo, cidades, modalidade, palavras-chave).
   Esses dois arquivos ficam de fora do Git de propósito (`.gitignore`), já
   que carregam seus dados pessoais reais.
2. Siga o [SETUP.md](SETUP.md) — há contas e credenciais que só você pode
   criar (Adzuna, senha de app do Gmail, OAuth do Google Drive).

## Estrutura

```
data/profile.example.json      modelo do banco de dados único (copie para profile.json e edite)
data/preferences.example.json  modelo dos critérios de busca (copie para preferences.json e edite)
src/search_adzuna.py      busca vagas na Adzuna API
src/classify.py           classifica cada vaga (adequação/modalidade/cidade/nível)
src/summarize.py          monta o resumo executivo + planilha (XLSX) completa
src/drive.py              upload dos resultados para o Google Drive
src/mailer.py             envio do e-mail diário (SMTP)
src/collect_feedback.py   acumula o feedback que você preenche nas planilhas (data/feedback_history.jsonl)
src/ssl_fix.py            faz o Python confiar no antivírus (ex.: Norton) que inspeciona HTTPS
src/cv/                   geração de CV em PDF customizado por vaga (Typst)
main.py                   orquestrador do fluxo diário
output/                   resultados e logs de cada execução (não versionado)
```

## Classificação: heurística + Claude só no topo

Com centenas de vagas por dia, classificar cada uma via Claude fica caro e
lento (415 vagas ≈ 33 min). Por isso o `classify.py` funciona em duas
etapas:

1. **Todas** as vagas passam pela heurística por palavras-chave (grátis,
   instantânea) — dá adequação, modalidade, cidade e nível pra todo mundo.
2. Só as **N mais promissoras** pela heurística (default 20, ajustável em
   `preferences.json` → `vagas_para_refinar_com_claude`) são reclassificadas
   via Claude, que escreve uma justificativa melhor e captura nuances que a
   heurística perde.

Isso reduziu o tempo de classificação de ~33 min para ~2 min no teste com
415 vagas reais, mantendo a qualidade nas vagas que mais importam.

### Feedback (base para um classificador futuro)

A lista completa tem uma coluna `feedback` em branco. **Importante**: o
`collect_feedback.py` só lê o XLSX local (`Desktop\Vagas\<data>\vagas.xlsx`)
— preencher a coluna na planilha do Google Sheets (a que vem linkada no
e-mail/Drive) não é capturado automaticamente ainda. Preencha com `bom` ou
`ruim` nas vagas que você já revisou no **arquivo local** (pode deixar o
resto em branco) e rode:

```bash
python src\collect_feedback.py
```

Isso acumula um histórico rotulado em `data/feedback_history.jsonl`. Ainda
não treina nada automaticamente — é a base de dados pra, quando acumular
uns 100-200 exemplos, treinar um classificador simples (scikit-learn) que
aprenda seu gosto de verdade e reduza ainda mais a dependência do Claude.

## Onde encontrar os resultados

Toda execução salva uma cópia local fácil de achar em `Desktop\Vagas\<data>\`
(resumo.md e vagas.xlsx) e os CVs gerados em `Desktop\Vagas\CVs\`. A cópia
"técnica" completa (incluindo logs) fica em `output/` dentro do projeto.

Quando o Drive está configurado, a lista completa sobe como uma **planilha
Google Sheets** (a cópia local é .xlsx) na pasta `Vagas/<data>/` do seu Drive — dá pra
abrir, filtrar e editar direto no navegador, inclusive a coluna `feedback`.
O e-mail diário linka essa planilha em vez de anexar um arquivo (só volta a
anexar o XLSX se o upload no Drive falhar naquele dia).

## Rodar manualmente

```bash
python main.py --dry-run   # busca + classifica, salva local, sem e-mail/Drive
python main.py              # fluxo completo
```

## Gerar um CV para uma vaga específica

```bash
python src\cv\build_cv.py --job-text "cole aqui a descrição da vaga" --empresa "Nome da Empresa" --cargo "Nome do Cargo"
```

O PDF sai em `output/cv/<empresa>_<cargo>/cv.pdf` (e uma cópia com o `.typ`
fonte e o JSON de dados em `Desktop\Vagas\CVs\<empresa>_<cargo>\`). Para
editar o layout, mexa em `src/cv/template.typ` (Typst) — os dados vêm de
`tailored_data.json`, gerado automaticamente a partir de `data/profile.json`
e priorizado para a vaga.

Os títulos e os cargos de cada experiência saem coloridos com a cor da
marca da empresa contratante, quando conhecida (`COMPANY_ACCENT_COLORS` em
`src/cv/build_cv.py` — só adiciono uma empresa ali depois de confirmar a cor
oficial, pra não chutar). Pra forçar uma cor específica: `--cor "#RRGGBB"`.
Links saem sempre em azul e sublinhados.

O layout é pensado pra ser bem lido por ATS/scrapers de vagas: sem colunas
nem texto lado a lado na mesma linha (esse tipo de truque visual costuma
embaralhar a ordem de leitura automática), e LinkedIn/GitHub aparecem como
texto literal (`linkedin.com/in/...`), não só como rótulo de link — assim
uma ferramenta que só lê o texto do PDF (sem seguir links) ainda consegue
capturar o endereço. Testei extraindo o texto do PDF programaticamente
(`pypdf`) pra confirmar que a ordem sai limpa antes de fechar essa mudança.

## Gerar uma carta de apresentação para uma vaga específica

```bash
python src\cv\build_cover_letter.py --job-text "cole aqui a descrição da vaga" --empresa "Nome da Empresa" --cargo "Nome do Cargo"
```

Requer `ANTHROPIC_API_KEY` (diferente do CV, uma carta de apresentação é
texto persuasivo customizado — sem LLM não vale a pena gerar). Sai em
`output/cv/<empresa>_<cargo>/carta_apresentacao.pdf`, na mesma pasta do CV
daquela vaga (e espelhada em `Desktop\Vagas\CVs\<pasta>\`), com a mesma cor
de marca.

## Atualizando seu perfil

Edite `data/profile.json` diretamente sempre que tiver uma nova experiência,
skill, projeto, certificação ou idioma. Esse arquivo é a fonte única de
verdade — tanto para a classificação de vagas quanto para o CV gerado.

`data/preferences.json` guarda níveis-alvo (Gerente com gestão / Especialista
II sem gestão), modalidade preferida, cidades aceitas e palavras-chave de
busca — ajuste livremente conforme sua busca evoluir.

## Agendamento (Windows Task Scheduler)

Rode uma vez como administrador (ou usuário comum, a tarefa roda no seu
contexto de usuário):

```powershell
powershell -ExecutionPolicy Bypass -File .\schedule_task.ps1
```

Isso cria uma tarefa chamada `AgenteRecolocacao` que roda `python main.py`
todo dia às 07:00 (ajustável no próprio script). A tarefa só executa
enquanto a máquina está ligada; se estiver desligada no horário, o Windows
não recupera a execução automaticamente (Task Scheduler não tem retry
embutido para isso — se for um problema, ative a opção "Executar assim que
possível após uma inicialização perdida" nas propriedades da tarefa, no
Agendador de Tarefas do Windows).

Logs de cada execução ficam em `output/logs/<data>.log`.

## Limitações conhecidas

- **Fontes de vagas**: só a Adzuna API está integrada. LinkedIn Jobs,
  Indeed, Catho, InfoJobs etc. não têm API pública estável e scraping
  automatizado viola os termos de uso dessas plataformas. O Gupy também não
  tem uma API pública de busca entre empresas (só por empresa, com token).
  Dá pra estender depois se topar aceitar a fragilidade de scraping direto
  em fontes específicas.
- **LinkedIn**: não há leitura automática do perfil (decisão deliberada,
  para não depender de sessão logada em execuções não supervisionadas).
  Atualize `data/profile.json` manualmente (ou peça pro seu assistente de
  IA fazer isso a partir do PDF exportado do seu perfil — Configurações →
  "Salvar como PDF" no LinkedIn).

## Licença

[MIT](LICENSE) — use, modifique e redistribua como quiser.
