# RPA RH — Envio de Cartão Ponto (P.A) — Unimed Vale do Aço

Automação desenvolvida pela **Digitaly Technology** para extração, separação e envio automático dos cartões de ponto aos colaboradores da **Unimed Vale do Aço**.

O projeto utiliza arquitetura limpa gerada via **Dig-cli**, com automação desktop baseada em **Visão Computacional e Imagem (OpenCV + PyAutoGUI)** integrada a uma API FastAPI e CLI para execuções agendadas e sob demanda.

---

## 📋 Regras de Negócio (PDD)

### 1. Frequência de Execução
- **Dias 04, 20 e 30** de cada mês (independente de ser dia útil, sábado, domingo ou feriado).

### 2. Períodos de Apuração das Datas
| Modo / Dia | Data Inicial | Data Final |
|---|---|---|
| **Dia 20** | Dia 20 do mês anterior | Dia 19 do mês atual |
| **Dia 30** | Dia 20 do mês anterior | Dia 19 do mês atual |
| **Dia 04** | Dia 20 do penúltimo mês | Dia 19 do mês anterior |

### 3. Comunicação por E-mail
- **Remetente:** `digitaly.tech@unimedvaledoaco.coop.br`
- **Dias 20 e 04:**
  - **Assunto:** `Espelho de Ponto – Conferência das Marcações`
  - **Mensagem:** Orientação para conferência das marcações com o gestor.
- **Dia 30:**
  - **Assunto:** `Espelho de Ponto – Fechamento do Período`
  - **Mensagem:** Envio do espelho de ponto finalizado.
- **Anexo:** Cartão de ponto individual em formato PDF correspondente à matrícula do colaborador.

### 4. Relatório de Controle da Execução
A cada execução é gerado um relatório Excel para auditoria no formato:
`DDMMAAAA-HHMM– Envio de Cartão Ponto.xlsx`
Contendo:
- `Data Execução`
- `Matrícula`
- `Colaborador`
- `Email`
- `Status` (Sucesso / Erro)
- `MotivoErro`

---

## 🛠️ Arquitetura do Projeto

```
EnvioCartaoPonto/
├── api/                        # Camada de Apresentação HTTP (FastAPI)
│   └── v1/
│       ├── endpoints/
│       │   ├── cartao_ponto.py # Endpoints de disparo e consulta
│       │   ├── automation.py   # Endpoints de automação visual
│       │   └── health.py       # Health check
│       └── dependencies/
├── core/                       # Configurações globais e logs
│   ├── config.py               # Variáveis de ambiente Pydantic Settings
│   └── logger.py               # Logger formatado
├── infrastructure/             # Camada de Infraestrutura
│   ├── automation/             # Helpers OpenCV + PyAutoGUI
│   │   ├── vision.py           # Visão computacional (OpenCV)
│   │   ├── gui.py              # Ações de GUI e mouse/teclado
│   │   └── recorder.py         # Gravador de macros
│   └── database/               # Banco SQLite local
├── services/                   # Regras de Negócio e Serviços
│   ├── senior_service.py       # Automação do sistema Senior Desktop por imagem
│   ├── pdf_splitter_service.py # Divisão do PDF consolidado por matrícula
│   ├── colaboradores_service.py# Leitura da planilha de colaboradores
│   ├── email_service.py        # Disparo SMTP com os templates do PDD
│   ├── relatorio_service.py    # Geração da planilha Excel de controle
│   └── orquestrador.py         # Orquestrador do fluxo end-to-end
├── schemas/                    # Schemas Pydantic (DTOs)
├── assets/templates/           # Templates visuais (PNG) para OpenCV
├── data/                       # Diretórios de armazenamento local / rede
│   ├── consolidado/            # PDFs consolidados extraídos
│   ├── individuais/            # PDFs individuais fatiados por matrícula
│   └── relatorios/             # Planilhas Excel de controle
├── rodar_local.py              # CLI para testes e execução pontual
├── manage.py                   # CLI administrativo
└── requirements.txt            # Dependências Python
```

---

## 🚀 Como Executar

### 1. Instalação das Dependências

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuração do `.env`

Copie o arquivo `.env.example` para `.env` e ajuste as credenciais do Senior e do SMTP:

```bash
cp .env.example .env
```

### 3. Execução Local via CLI (`rodar_local.py`)

```bash
# Execução automática baseada na data de hoje
python rodar_local.py

# Simulação das datas do dia 20
python rodar_local.py --modo 20

# Simulação das datas do dia 30
python rodar_local.py --modo 30

# Simulação das datas do dia 04
python rodar_local.py --modo 04

# Executar sem disparar e-mails reais (modo simulação/teste)
python rodar_local.py --sem-email

# Testar apenas uma matrícula específica
python rodar_local.py --matricula 1001 --sem-senior
```

### 4. Execução da API FastAPI

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Documentação Swagger interativa:
👉 `http://localhost:8000/docs`
