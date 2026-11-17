#!/usr/bin/env python
"""
manage.py — CLI interno de gerenciamento do projeto / Internal project management CLI.
Execute a partir da raiz do projeto / Run from the project root:

  python manage.py <comando> [opções]

Comandos disponíveis / Available commands:
  run            Inicia o servidor de desenvolvimento / Start dev server
  add-resource   Scaffold completo com banco de dados / Full resource with DB layer
  add-service    Apenas lógica de negócio, sem banco / Business logic only, no DB
  add-middleware Scaffold de middleware customizado / Custom middleware scaffold
  add-proxy      Cliente HTTP para API externa / HTTP client for external API
  routes         Lista rotas registradas / List registered routes
  migrate        Gera e aplica migration Alembic / Generate and apply Alembic migration
  test           Executa os testes / Run test suite

Use  python manage.py <comando> --help  para detalhes de cada comando.
Use  python manage.py <command> --help  for details on each command.
"""
import sys
import subprocess
import typer
from pathlib import Path

# Garante suporte a UTF-8 sem erro charmap no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

app = typer.Typer(
    name="manage",
    help=(
        "CLI de gerenciamento do projeto FastAPI.\n\n"
        "FastAPI project management CLI.\n\n"
        "Execute 'python manage.py <comando> --help' para detalhes.\n"
        "Run 'python manage.py <command> --help' for details."
    ),
    add_completion=False,
    no_args_is_help=True,
)


def _ok(m):   typer.echo(typer.style("  [OK] " + str(m), fg=typer.colors.GREEN))
def _info(m): typer.echo(typer.style("  [..] " + str(m), fg=typer.colors.CYAN))
def _warn(m): typer.echo(typer.style("  [!]  " + str(m), fg=typer.colors.YELLOW))
def _err(m):  typer.echo(typer.style("  [X]  " + str(m), fg=typer.colors.RED))
def _sec(t):  typer.echo(typer.style("\n  == " + t, bold=True))


def _write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _touch(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()


def _to_class(name):
    return "".join(w.capitalize() for w in name.split("_"))


def _check_root():
    if not Path("main.py").exists():
        _err("main.py não encontrado. Execute na raiz do projeto.")
        _err("main.py not found. Run from the project root.")
        raise typer.Exit(1)


# ════════════════════════════════════════════════════════════════
# run
# ════════════════════════════════════════════════════════════════

@app.command()
def run(
    port:    int  = typer.Option(8000,        "--port",   "-p",  help="Porta do servidor / Server port"),
    host:    str  = typer.Option("127.0.0.1", "--host",          help="Host do servidor / Server host"),
    reload:  bool = typer.Option(True,  "--reload/--no-reload",   help="Hot-reload ao salvar / Hot-reload on save"),
    workers: int  = typer.Option(1,     "--workers", "-w",        help="Número de workers / Worker count"),
):
    """
    Inicia o servidor uvicorn de desenvolvimento.
    Start the uvicorn development server.

    \b
    Exemplos / Examples:
      python manage.py run
      python manage.py run --port 8080 --no-reload
      python manage.py run --workers 4 --host 0.0.0.0
    """
    cmd = [sys.executable, "-m", "uvicorn", "main:app",
           "--host", host, "--port", str(port), "--workers", str(workers)]
    if reload:
        cmd.append("--reload")
    _info("http://" + host + ":" + str(port) + "  (reload=" + str(reload) + ", workers=" + str(workers) + ")")
    subprocess.run(cmd)


# ════════════════════════════════════════════════════════════════
# add-resource  (completo, com banco de dados)
# ════════════════════════════════════════════════════════════════

@app.command()
def add_resource(
    name: str = typer.Argument(
        ...,
        help=(
            "Nome do recurso em snake_case singular.\n"
            "Resource name in singular snake_case.\n"
            "Ex: product, user_profile, sales_order"
        ),
    ),
    auth:      bool = typer.Option(False, "--auth/--no-auth",
        help="Protege as rotas com autenticação / Protect routes with auth dependency"),
    dto:       bool = typer.Option(True,  "--dto/--no-dto",
        help="Gera schemas Pydantic (Create/Update/Response) / Generate Pydantic schemas"),
    repo:      bool = typer.Option(True,  "--repo/--no-repo",
        help="Gera Repository com acesso ao banco / Generate Repository with DB access"),
    proxy:     bool = typer.Option(False, "--proxy/--no-proxy",
        help="Gera cliente HTTP para API externa / Generate HTTP client for external API"),
    events:    bool = typer.Option(False, "--events/--no-events",
        help="Emite evento de domínio ao criar / Emit domain event on create"),
    paginated: bool = typer.Option(True,  "--paginated/--no-paginated",
        help="Retorna lista paginada / Return paginated list response"),
    version:   str  = typer.Option("v1",  "--version",
        help="Versão da API / API version prefix (ex: v1, v2)"),
):
    """
    Scaffold COMPLETO: model ORM + schema + repository + service + endpoint HTTP.
    FULL scaffold: ORM model + schema + repository + service + HTTP endpoint.

    \b
    Gerado / Generated:
      models/<name>.py              → SQLAlchemy ORM model
      schemas/<name>.py             → Pydantic DTOs (Create / Update / Response)
      repositories/<name>_repository.py → Repository Pattern com SQLAlchemy
      services/<name>_service.py    → Regras de negócio / Business logic
      api/v1/endpoints/<name>.py    → Rotas HTTP (GET/POST/PUT/DELETE)

    \b
    Use quando / Use when:
      ✔ O recurso precisa persistir dados no banco de dados
      ✔ The resource needs to persist data in the database

    \b
    Exemplos / Examples:
      python manage.py add-resource product
      python manage.py add-resource order --auth --events --paginated
      python manage.py add-resource payment --proxy --no-repo
      python manage.py add-resource log_entry --no-dto --no-paginated
    """
    _check_root()
    base = Path(".")
    cap  = _to_class(name)
    typer.echo(typer.style("\nRecurso completo / Full resource: " + name + " (" + cap + ")\n", bold=True))

    if dto:
        _gen_schemas(base, name, cap)
        _ok("schemas/" + name + ".py")

    # model e repo só quando --repo está ativo
    if repo:
        _gen_model(base, name, cap)
        _ok("models/" + name + ".py")
        _gen_repository(base, name, cap)
        _ok("repositories/" + name + "_repository.py")
    else:
        _warn("--no-repo: model e repository não gerados / model and repository not generated")

    _gen_service(base, name, cap, dto, repo, events, paginated)
    _ok("services/" + name + "_service.py")

    if proxy:
        _gen_proxy(base, name, cap)
        _ok("infrastructure/http/" + name + "_client.py")

    _gen_endpoint(base, name, cap, auth, dto, paginated, version)
    _ok("api/" + version + "/endpoints/" + name + ".py")
    _register(base, name, version)
    _ok("Rota registrada / Route registered: /" + name + "s")

    typer.echo(typer.style("\n✅  '" + name + "' pronto! / ready!\n", fg=typer.colors.GREEN, bold=True))


# ════════════════════════════════════════════════════════════════
# add-service  (lógica de negócio pura, sem banco)
# ════════════════════════════════════════════════════════════════

@app.command()
def add_service(
    name: str = typer.Argument(
        ...,
        help=(
            "Nome do serviço em snake_case singular.\n"
            "Service name in singular snake_case.\n"
            "Ex: pricing, notification, tax_calculator"
        ),
    ),
    dto:    bool = typer.Option(True,  "--dto/--no-dto",
        help="Gera schemas Pydantic de entrada/saída / Generate Pydantic input/output schemas"),
    events: bool = typer.Option(False, "--events/--no-events",
        help="Emite eventos de domínio / Emit domain events"),
    inject: str  = typer.Option("",   "--inject",
        help=(
            "Dependências externas a injetar, separadas por vírgula.\n"
            "External dependencies to inject, comma-separated.\n"
            "Ex: --inject order_service,product_service"
        )),
):
    """
    Scaffold LEVE: apenas schema + service com lógica de negócio pura.
    LIGHTWEIGHT scaffold: schema + pure business logic service only.

    \b
    NÃO gera / Does NOT generate:
      ✘ Model ORM (sem acesso direto ao banco)
      ✘ Repository
      ✘ Endpoint HTTP
      ✘ ORM Model (no direct DB access)

    \b
    GERA / Generates:
      schemas/<name>.py          → DTOs de entrada e saída / Input & output DTOs
      services/<name>_service.py → Lógica de negócio pura / Pure business logic

    \b
    Use quando / Use when:
      ✔ Regra de negócio que consome dados de outros serviços/repositórios já existentes
      ✔ Cálculos, validações, orquestrações, notificações internas
      ✔ Business rule that consumes data from existing services/repositories
      ✔ Calculations, validations, orchestrations, internal notifications

    \b
    Como consumir / How to consume:
      # Em outro serviço / In another service:
      from services.pricing_service import PricingService
      svc = PricingService(order_service=order_svc, product_service=product_svc)

      # Em um endpoint / In an endpoint:
      def _svc(order_svc=Depends(get_order_service)) -> PricingService:
          return PricingService(order_service=order_svc)

    \b
    Exemplos / Examples:
      python manage.py add-service pricing
      python manage.py add-service notification --events
      python manage.py add-service tax_calculator --inject order_service,product_service
      python manage.py add-service discount_engine --dto --events
    """
    _check_root()
    base = Path(".")
    cap  = _to_class(name)
    typer.echo(typer.style("\nServiço leve / Lightweight service: " + name + " (" + cap + ")\n", bold=True))

    deps = [d.strip() for d in inject.split(",") if d.strip()] if inject else []

    if dto:
        _gen_service_schemas(base, name, cap)
        _ok("schemas/" + name + ".py")

    _gen_pure_service(base, name, cap, dto, events, deps)
    _ok("services/" + name + "_service.py")

    typer.echo(typer.style("\n✅  '" + name + "' pronto! / ready!\n", fg=typer.colors.GREEN, bold=True))

    if deps:
        _info("Injetar no endpoint / Inject in endpoint:")
        for d in deps:
            _info("  from services." + d + "_service import " + _to_class(d) + "Service")
    _info("Importar onde precisar / Import wherever needed:")
    _info("  from services." + name + "_service import " + cap + "Service")


# ════════════════════════════════════════════════════════════════
# add-middleware
# ════════════════════════════════════════════════════════════════

@app.command()
def add_middleware(
    name: str = typer.Argument(
        ...,
        help="Nome do middleware em snake_case / Middleware name in snake_case. Ex: rate_limit, cors_custom"
    ),
):
    """
    Scaffold de middleware Starlette customizado.
    Scaffold a custom Starlette middleware.

    \b
    Gerado / Generated:
      middlewares/<name>.py → Classe middleware pronta para implementar

    \b
    Após criar, registre em main.py / After creating, register in main.py:
      app.add_middleware(<Name>Middleware)

    \b
    Exemplos / Examples:
      python manage.py add-middleware rate_limit
      python manage.py add-middleware request_id
      python manage.py add-middleware audit_log
    """
    cap = _to_class(name)
    content = "\n".join([
        "import logging",
        "from fastapi import Request",
        "from starlette.middleware.base import BaseHTTPMiddleware",
        "",
        "logger = logging.getLogger(__name__)",
        "",
        "",
        "class " + cap + "Middleware(BaseHTTPMiddleware):",
        '    """',
        "    Middleware: " + name + ".",
        "    TODO: implemente a lógica abaixo / implement logic below.",
        '    """',
        "",
        "    async def dispatch(self, request: Request, call_next):",
        "        # --- pré-processamento / pre-processing ---",
        "        response = await call_next(request)",
        "        # --- pós-processamento / post-processing ---",
        "        return response",
        "",
    ])
    _write(Path("middlewares") / (name + ".py"), content)
    _ok("middlewares/" + name + ".py")
    _warn("Registre em main.py / Register in main.py:  app.add_middleware(" + cap + "Middleware)")


# ════════════════════════════════════════════════════════════════
# add-proxy
# ════════════════════════════════════════════════════════════════

@app.command()
def add_proxy(
    name:     str = typer.Argument(
        ...,
        help="Nome do cliente em snake_case / Client name in snake_case. Ex: payment_gateway, erp_api"
    ),
    base_url: str = typer.Option(
        "https://api.example.com", "--url",
        help="URL base da API externa / Base URL of the external API"
    ),
):
    """
    Scaffold de cliente HTTP assíncrono (httpx) para API externa.
    Scaffold an async httpx HTTP client for an external API.

    \b
    Gerado / Generated:
      infrastructure/http/<name>_client.py → Cliente com métodos CRUD

    \b
    Exemplos / Examples:
      python manage.py add-proxy payment_gateway --url https://api.stripe.com
      python manage.py add-proxy erp_api --url https://erp.empresa.com/api
    """
    _gen_proxy(Path("."), name, _to_class(name), base_url)
    _ok("infrastructure/http/" + name + "_client.py")


# ════════════════════════════════════════════════════════════════
# routes
# ════════════════════════════════════════════════════════════════

@app.command()
def routes(
    version: str = typer.Option("v1", "--version", help="Versão da API / API version. Ex: v1, v2"),
):
    """
    Lista todas as rotas HTTP registradas.
    List all registered HTTP routes.

    \b
    Exemplos / Examples:
      python manage.py routes
      python manage.py routes --version v2
    """
    init = Path("api") / version / "__init__.py"
    if not init.exists():
        _err("api/" + version + "/__init__.py não encontrado / not found.")
        raise typer.Exit(1)
    typer.echo(typer.style("\nRotas registradas / Registered routes  (api/" + version + ")\n", bold=True))
    for line in init.read_text(encoding="utf-8").splitlines():
        if "include_router" in line:
            typer.echo("  " + line.strip())
    typer.echo()


# ════════════════════════════════════════════════════════════════
# migrate
# ════════════════════════════════════════════════════════════════

@app.command()
def migrate(
    msg:    str  = typer.Option("auto", "-m", "--msg",  help="Mensagem da migration / Migration message"),
    init:   bool = typer.Option(False, "--init",         help="Inicializa Alembic do zero / Initialize Alembic from scratch"),
    only_gen: bool = typer.Option(False, "--only-gen",   help="Só gera o arquivo, não aplica / Only generate, do not apply"),
):
    """
    Gera e aplica migrations Alembic. Inicializa automaticamente se necessário.
    Generate and apply Alembic migrations. Auto-initializes if needed.

    \b
    O que faz / What it does:
      1. Verifica se alembic.ini existe, se não: inicializa automaticamente
      2. Gera nova revision com --autogenerate
      3. Aplica com upgrade head (a menos que --only-gen)

    \b
    Equivalente a / Equivalent to:
      alembic revision --autogenerate -m <msg>
      alembic upgrade head

    \b
    Exemplos / Examples:
      python manage.py migrate
      python manage.py migrate -m "add product table"
      python manage.py migrate --init          # força reinicialização
      python manage.py migrate --only-gen -m "draft"
    """
    ini_path = Path("alembic.ini")
    env_path = Path("infrastructure") / "database" / "migrations" / "env.py"

    # ── auto-init if alembic.ini is missing or --init forced ──────
    if init or not ini_path.exists():
        _info("Inicializando Alembic / Initializing Alembic...")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "init", "infrastructure/database/migrations"],
            capture_output=True, text=True,
        )
        if result.returncode != 0 and "already exists" not in result.stderr:
            _err("Falha ao inicializar Alembic / Failed to initialize Alembic:")
            _err(result.stderr)
            raise typer.Exit(1)

        # ── patch alembic.ini: set script_location ─────────────────
        ini_content = ini_path.read_text(encoding="utf-8")
        ini_content = ini_content.replace(
            "script_location = alembic",
            "script_location = infrastructure/database/migrations",
        )
        ini_path.write_text(ini_content, encoding="utf-8")
        _ok("alembic.ini configurado / configured")

        # ── patch env.py: inject async engine + target_metadata ────
        _write_alembic_env(env_path)
        _ok("infrastructure/database/migrations/env.py configurado / configured")

    else:
        # ── ensure env.py is up-to-date even without --init ────────
        if env_path.exists():
            env_txt = env_path.read_text(encoding="utf-8")
            if "run_async_migrations" not in env_txt:
                _warn("env.py desatualizado, atualizando / outdated, updating...")
                _write_alembic_env(env_path)
                _ok("env.py atualizado / updated")

    # ── generate revision ──────────────────────────────────────────
    _info("Gerando revision / Generating revision: \"" + msg + "\"")
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m", msg],
    )
    if r.returncode != 0:
        _err("Falha ao gerar revision / Failed to generate revision")
        raise typer.Exit(1)

    if only_gen:
        _warn("--only-gen: migration gerada mas NÃO aplicada / generated but NOT applied")
        return

    # ── apply ──────────────────────────────────────────────────────
    _info("Aplicando / Applying: upgrade head")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"])



_ALEMBIC_ENV_PY = 'import asyncio\nimport sys\nimport os\nfrom logging.config import fileConfig\nfrom pathlib import Path\nfrom sqlalchemy import pool\nfrom sqlalchemy.engine import Connection\nfrom sqlalchemy.ext.asyncio import async_engine_from_config\nfrom alembic import context\n\n_root = Path(__file__).parent.parent.parent.parent\nif str(_root) not in sys.path:\n    sys.path.insert(0, str(_root))\n\n_env_file = _root / ".env"\nif _env_file.exists():\n    for _line in _env_file.read_text(encoding="utf-8").splitlines():\n        _line = _line.strip()\n        if _line and not _line.startswith("#") and "=" in _line:\n            _k, _, _v = _line.partition("=")\n            os.environ.setdefault(_k.strip(), _v.strip())\n\nfrom infrastructure.database.base import Base\nimport importlib\nimport pkgutil\n\n_models_dir = _root / "models"\nif _models_dir.exists():\n    for _mod in pkgutil.iter_modules([str(_models_dir)]):\n        importlib.import_module("models." + _mod.name)\n\nconfig = context.config\nif config.config_file_name is not None:\n    fileConfig(config.config_file_name)\n\ntarget_metadata = Base.metadata\n\n\ndef _get_url() -> str:\n    try:\n        from core.config import settings\n        return settings.DATABASE_URL\n    except Exception:\n        url = os.environ.get("DATABASE_URL", "")\n        if not url:\n            raise RuntimeError(\n                "DATABASE_URL nao encontrada. Defina no arquivo .env\\n"\n                "DATABASE_URL not found. Define it in the .env file"\n            )\n        return url\n\n\ndef run_migrations_offline() -> None:\n    context.configure(\n        url=_get_url(),\n        target_metadata=target_metadata,\n        literal_binds=True,\n        dialect_opts={"paramstyle": "named"},\n    )\n    with context.begin_transaction():\n        context.run_migrations()\n\n\ndef do_run_migrations(connection: Connection) -> None:\n    context.configure(connection=connection, target_metadata=target_metadata)\n    with context.begin_transaction():\n        context.run_migrations()\n\n\nasync def run_async_migrations() -> None:\n    cfg = config.get_section(config.config_ini_section, {})\n    cfg["sqlalchemy.url"] = _get_url()\n    engine = async_engine_from_config(\n        cfg, prefix="sqlalchemy.", poolclass=pool.NullPool,\n    )\n    async with engine.connect() as conn:\n        await conn.run_sync(do_run_migrations)\n    await engine.dispose()\n\n\ndef run_migrations_online() -> None:\n    asyncio.run(run_async_migrations())\n\n\nif context.is_offline_mode():\n    run_migrations_offline()\nelse:\n    run_migrations_online()\n'


def _write_alembic_env(env_path):
    """Escreve env.py async com carregamento do .env."""
    import pathlib as _pl
    p = _pl.Path(env_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_ALEMBIC_ENV_PY, encoding="utf-8")


def _gen_schemas(base, name, cap):
    out = [
        "from pydantic import BaseModel, Field, ConfigDict",
        "from typing import Optional",
        "from datetime import datetime",
        "",
        "",
        "class " + cap + "Base(BaseModel):",
        "    model_config = ConfigDict(from_attributes=True)",
        "    name:        str           = Field(..., min_length=1, max_length=255)",
        "    description: Optional[str] = Field(None, max_length=1000)",
        "",
        "",
        "class " + cap + "Create(" + cap + "Base):",
        "    pass",
        "",
        "",
        "class " + cap + "Update(BaseModel):",
        "    model_config = ConfigDict(from_attributes=True)",
        "    name:        Optional[str] = Field(None, min_length=1, max_length=255)",
        "    description: Optional[str] = Field(None, max_length=1000)",
        "",
        "",
        "class " + cap + "Response(" + cap + "Base):",
        "    id:         int",
        "    created_at: Optional[datetime] = None",
        "    updated_at: Optional[datetime] = None",
        "",
    ]
    _write(base / "schemas" / (name + ".py"), "\n".join(out))


def _gen_model(base, name, cap):
    out = [
        "from sqlalchemy import String, Text, Integer",
        "from sqlalchemy.orm import Mapped, mapped_column",
        "from infrastructure.database.base import Base, TimestampMixin",
        "",
        "",
        "class " + cap + "(Base, TimestampMixin):",
        '    __tablename__ = "' + name + 's"',
        "",
        "    id:          Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)",
        "    name:        Mapped[str]        = mapped_column(String(255), nullable=False, index=True)",
        "    description: Mapped[str | None] = mapped_column(Text, nullable=True)",
        "",
        "    def __repr__(self) -> str:",
        '        return f"<' + cap + ' id={self.id} name={self.name!r}>"',
        "",
    ]
    _write(base / "models" / (name + ".py"), "\n".join(out))


def _gen_repository(base, name, cap):
    out = [
        "import logging",
        "from typing import Sequence",
        "from sqlalchemy import select, func",
        "from sqlalchemy.ext.asyncio import AsyncSession",
        "from models." + name + " import " + cap,
        "",
        "logger = logging.getLogger(__name__)",
        "",
        "",
        "class " + cap + "Repository:",
        "    def __init__(self, session: AsyncSession):",
        "        self._session = session",
        "",
        "    async def count(self) -> int:",
        "        r = await self._session.execute(select(func.count()).select_from(" + cap + "))",
        "        return r.scalar_one()",
        "",
        "    async def list(self, offset: int = 0, limit: int = 20) -> Sequence[" + cap + "]:",
        "        r = await self._session.execute(",
        "            select(" + cap + ").order_by(" + cap + ".id).offset(offset).limit(limit)",
        "        )",
        "        return r.scalars().all()",
        "",
        "    async def get(self, id: int) -> " + cap + " | None:",
        "        return await self._session.get(" + cap + ", id)",
        "",
        "    async def add(self, entity: " + cap + ") -> " + cap + ":",
        "        self._session.add(entity)",
        "        await self._session.flush()",
        "        await self._session.refresh(entity)",
        '        logger.info("Created ' + cap + ' id=%d", entity.id)',
        "        return entity",
        "",
        "    async def update(self, entity: " + cap + ", data: dict) -> " + cap + ":",
        "        for k, v in data.items():",
        "            if v is not None:",
        "                setattr(entity, k, v)",
        "        await self._session.flush()",
        "        await self._session.refresh(entity)",
        "        return entity",
        "",
        "    async def delete(self, entity: " + cap + ") -> None:",
        "        await self._session.delete(entity)",
        "        await self._session.flush()",
        '        logger.info("Deleted ' + cap + ' id=%d", entity.id)',
        "",
    ]
    _write(base / "repositories" / (name + "_repository.py"), "\n".join(out))


def _gen_service(base, name, cap, with_dto, with_repo, with_events, paginated):
    imports = [
        "import logging",
        "from core.exceptions import NotFoundException",
        "from core.responses import PaginatedResponse",
    ]
    if with_dto:
        imports.append("from schemas." + name + " import " + cap + "Create, " + cap + "Update")
    if with_repo:
        imports.append("from repositories." + name + "_repository import " + cap + "Repository")
    if with_events:
        imports.append("from infrastructure.events.bus import bus, DomainEvent")

    ct = cap + "Create" if with_dto else "dict"
    ut = cap + "Update" if with_dto else "dict"

    body = imports + [
        "",
        "logger = logging.getLogger(__name__)",
        "",
        "",
        "def _to_dict(obj) -> dict:",
        "    return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}",
        "",
        "",
        "class " + cap + "Service:",
        "    def __init__(self, repository):",
        "        self._repo = repository",
        "",
        "    async def list(self, page: int = 1, page_size: int = 20) -> dict:",
        "        offset = (page - 1) * page_size",
        "        items  = await self._repo.list(offset=offset, limit=page_size)",
        "        total  = await self._repo.count()",
        "        return PaginatedResponse.build(",
        "            items=[_to_dict(i) for i in items],",
        "            total=total, page=page, page_size=page_size,",
        "        ).model_dump()",
        "",
        "    async def create(self, data: " + ct + ") -> dict:",
        "        from models." + name + " import " + cap,
        "        payload = data.model_dump() if hasattr(data, 'model_dump') else data",
        "        entity  = " + cap + "(**payload)",
        "        result  = await self._repo.add(entity)",
    ]
    if with_events:
        body.append(
            "        await bus.publish(DomainEvent('" + name + ".created', {'id': result.id}))"
        )
    body += [
        "        return _to_dict(result)",
        "",
        "    async def get(self, id: int) -> dict:",
        "        entity = await self._repo.get(id)",
        "        if not entity:",
        '            raise NotFoundException("' + cap + '", id)',
        "        return _to_dict(entity)",
        "",
        "    async def update(self, id: int, data: " + ut + ") -> dict:",
        "        entity = await self._repo.get(id)",
        "        if not entity:",
        '            raise NotFoundException("' + cap + '", id)',
        "        patch  = data.model_dump(exclude_unset=True) if hasattr(data, 'model_dump') else data",
        "        result = await self._repo.update(entity, patch)",
        "        return _to_dict(result)",
        "",
        "    async def delete(self, id: int) -> None:",
        "        entity = await self._repo.get(id)",
        "        if not entity:",
        '            raise NotFoundException("' + cap + '", id)',
        "        await self._repo.delete(entity)",
        "",
    ]
    _write(base / "services" / (name + "_service.py"), "\n".join(body))


# ════════════════════════════════════════════════════════════════
# Scaffold helpers — add-service (lógica pura / pure logic)
# ════════════════════════════════════════════════════════════════

def _gen_service_schemas(base, name, cap):
    """DTOs simples de entrada/saída, sem from_attributes (não mapeiam ORM)."""
    out = [
        "from pydantic import BaseModel, Field",
        "from typing import Optional, Any",
        "",
        "",
        "# --- Input / Entrada ---",
        "",
        "class " + cap + "Input(BaseModel):",
        '    """Dados de entrada para ' + name + ' / Input data for ' + name + '."""',
        "    # TODO: defina os campos de entrada / define input fields",
        "    payload: dict[str, Any] = Field(default_factory=dict)",
        "",
        "",
        "# --- Output / Saída ---",
        "",
        "class " + cap + "Output(BaseModel):",
        '    """Resultado do serviço ' + name + ' / Output of ' + name + ' service."""',
        "    # TODO: defina os campos de saída / define output fields",
        "    result: dict[str, Any] = Field(default_factory=dict)",
        "    success: bool = True",
        "    message: Optional[str] = None",
        "",
    ]
    _write(base / "schemas" / (name + ".py"), "\n".join(out))


def _gen_pure_service(base, name, cap, with_dto, with_events, deps):
    imports = ["import logging"]
    if with_dto:
        imports.append("from schemas." + name + " import " + cap + "Input, " + cap + "Output")
    if with_events:
        imports.append("from infrastructure.events.bus import bus, DomainEvent")

    dep_args = []
    dep_assigns = []
    dep_type_hints = []
    for d in deps:
        dep_cap = _to_class(d)
        dep_args.append(d + "_service")
        dep_assigns.append("        self._" + d + " = " + d + "_service")
        dep_type_hints.append("        # self._" + d + ": " + dep_cap + "Service")

    init_params = ", ".join(dep_args)
    if init_params:
        init_params = ", " + init_params

    in_t  = cap + "Input"  if with_dto else "dict"
    out_t = cap + "Output" if with_dto else "dict"

    body = imports + [
        "",
        "logger = logging.getLogger(__name__)",
        "",
        "",
        "class " + cap + "Service:",
        '    """',
        "    Serviço de lógica de negócio: " + name + ".",
        "    Pure business logic service: " + name + ".",
        "",
        "    Não acessa banco diretamente — consome outros serviços/repositórios.",
        "    Does not access DB directly — consumes other services/repositories.",
        '    """',
        "",
        "    def __init__(self" + init_params + "):",
    ]

    if dep_assigns:
        body += dep_assigns
    else:
        body.append("        pass  # injete dependências conforme necessário / inject dependencies as needed")

    body += [
        "",
        "    async def execute(self, data: " + in_t + ") -> " + out_t + ":",
        '        """',
        "        Ponto de entrada principal do serviço.",
        "        Main entry point of the service.",
        '        """',
        "        logger.info(\"Executing " + name + " service\")",
        "",
        "        # TODO: implemente a lógica de negócio / implement business logic",
        "        payload = data.payload if hasattr(data, 'payload') else data",
        "",
    ]

    if with_events:
        body += [
            "        # Emitir evento de domínio / Emit domain event",
            "        await bus.publish(DomainEvent('" + name + ".executed', {'payload': str(payload)}))",
            "",
        ]

    if with_dto:
        body += [
            "        return " + cap + "Output(result=payload, success=True)",
            "",
        ]
    else:
        body += [
            "        return {'result': payload, 'success': True}",
            "",
        ]

    _write(base / "services" / (name + "_service.py"), "\n".join(body))


# ════════════════════════════════════════════════════════════════
# Scaffold helpers — proxy / http client
# ════════════════════════════════════════════════════════════════

def _gen_proxy(base, name, cap, base_url="https://api.example.com"):
    _touch(base / "infrastructure" / "http" / "__init__.py")
    bc = base / "infrastructure" / "http" / "base_client.py"
    if not bc.exists():
        _write(bc, "\n".join([
            "import logging",
            "import httpx",
            "from typing import Any",
            "",
            "logger = logging.getLogger(__name__)",
            "",
            "",
            "class BaseHttpClient:",
            '    base_url: str  = ""',
            "    timeout: float = 10.0",
            "",
            "    def __init__(self):",
            "        self._client: httpx.AsyncClient | None = None",
            "",
            "    async def start(self):",
            "        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)",
            "",
            "    async def stop(self):",
            "        if self._client:",
            "            await self._client.aclose()",
            "",
            "    async def get(self, p, **kw):    return await self._req('GET',    p, **kw)",
            "    async def post(self, p, **kw):   return await self._req('POST',   p, **kw)",
            "    async def put(self, p, **kw):    return await self._req('PUT',    p, **kw)",
            "    async def delete(self, p, **kw): return await self._req('DELETE', p, **kw)",
            "",
            "    async def _req(self, method, path, **kw):",
            "        resp = await self._client.request(method, path, **kw)",
            "        resp.raise_for_status()",
            "        return resp.json()",
            "",
        ]))

    _write(base / "infrastructure" / "http" / (name + "_client.py"), "\n".join([
        "from infrastructure.http.base_client import BaseHttpClient",
        "",
        "",
        "class " + cap + "Client(BaseHttpClient):",
        '    base_url = "' + base_url + '"',
        "",
        "    async def list(self):",
        '        return await self.get("/' + name + 's")',
        "",
        "    async def get_one(self, id: int):",
        '        return await self.get(f"/' + name + 's/{id}")',
        "",
        "    async def create(self, data: dict):",
        '        return await self.post("/' + name + 's", json=data)',
        "",
        "    async def update(self, id: int, data: dict):",
        '        return await self.put(f"/' + name + 's/{id}", json=data)',
        "",
        "    async def remove(self, id: int):",
        '        return await self.delete(f"/' + name + 's/{id}")',
        "",
        "",
        name + "_client = " + cap + "Client()",
        "",
    ]))


# ════════════════════════════════════════════════════════════════
# Scaffold helpers — endpoint + router registration
# ════════════════════════════════════════════════════════════════

def _gen_endpoint(base, name, cap, use_auth, with_dto, paginated, version):
    lines = [
        "from fastapi import APIRouter, Depends, status",
        "from api.v1.dependencies.pagination import PaginationParams, get_pagination",
        "from infrastructure.database.session import get_db",
        "from repositories." + name + "_repository import " + cap + "Repository",
        "from services." + name + "_service import " + cap + "Service",
    ]
    if use_auth:
        lines.append("from api.v1.dependencies.auth import get_current_user")
    if with_dto:
        lines.append("from schemas." + name + " import " + cap + "Create, " + cap + "Update")

    ct = cap + "Create" if with_dto else "dict"
    ut = cap + "Update" if with_dto else "dict"
    auth_dep = ", current_user: dict = Depends(get_current_user)" if use_auth else ""

    lines += [
        "",
        "router = APIRouter()",
        "",
        "",
        "def _svc(db=Depends(get_db)) -> " + cap + "Service:",
        "    return " + cap + "Service(" + cap + "Repository(db))",
        "",
        "",
        '@router.get("/", summary="List ' + name + 's")',
        "async def list_" + name + "s(",
        "    pagination: PaginationParams = Depends(get_pagination),",
        "    svc: " + cap + "Service = Depends(_svc)" + auth_dep + ",",
        "):",
        "    return await svc.list(page=pagination.page, page_size=pagination.page_size)",
        "",
        "",
        '@router.post("/", status_code=status.HTTP_201_CREATED, summary="Create ' + name + '")',
        "async def create_" + name + "(data: " + ct + ", svc: " + cap + "Service = Depends(_svc)" + auth_dep + "):",
        "    return await svc.create(data)",
        "",
        "",
        '@router.get("/{id}", summary="Get ' + name + '")',
        "async def get_" + name + "(id: int, svc: " + cap + "Service = Depends(_svc)" + auth_dep + "):",
        "    return await svc.get(id)",
        "",
        "",
        '@router.put("/{id}", summary="Update ' + name + '")',
        "async def update_" + name + "(id: int, data: " + ut + ", svc: " + cap + "Service = Depends(_svc)" + auth_dep + "):",
        "    return await svc.update(id, data)",
        "",
        "",
        '@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete ' + name + '")',
        "async def delete_" + name + "(id: int, svc: " + cap + "Service = Depends(_svc)" + auth_dep + "):",
        "    await svc.delete(id)",
        "",
    ]
    _touch(base / "api" / version / "endpoints" / "__init__.py")
    _write(base / "api" / version / "endpoints" / (name + ".py"), "\n".join(lines))


def _register(base, name, version):
    init = base / "api" / version / "__init__.py"
    if not init.exists():
        _err("api/" + version + "/__init__.py não encontrado / not found.")
        raise typer.Exit(1)
    content = init.read_text(encoding="utf-8")
    imp = "from api." + version + ".endpoints." + name + " import router as " + name + "_router\n"
    inc = 'router.include_router(' + name + '_router, prefix="/' + name + 's", tags=["' + name + '"])\n'
    if imp.strip() in content:
        _warn("'" + name + "' já registrado / already registered.")
        return
    lines = content.splitlines(keepends=True)
    lines.insert(0, imp)
    lines.append(inc)
    init.write_text("".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────────────────────


# ── Automation commands (auto-added) ─────────────────────
@app.command("automate-shot")
def automate_shot(
    out: str = typer.Option("screenshot.png", "--out", "-o",
        help="Caminho de saída / Output path"),
    region: str = typer.Option("", "--region",
        help="Região 'x,y,w,h' (opcional) / Region (optional)"),
):
    """Captura screenshot via PyAutoGUI."""
    from infrastructure.automation import gui
    reg = None
    if region:
        parts = [int(p) for p in region.split(",")]
        if len(parts) != 4:
            _err("--region deve ser 'x,y,w,h'")
            raise typer.Exit(1)
        reg = tuple(parts)
    gui.screenshot(region=reg, save_to=out)
    _ok("Screenshot salva em / saved to: " + out)

@app.command("automate-find")
def automate_find(
    image:    str = typer.Option(...,  "--image",    help="Imagem onde buscar"),
    template: str = typer.Option(...,  "--template", help="Imagem a localizar"),
    threshold: float = typer.Option(0.85, "--threshold"),
):
    """Localiza template em imagem usando OpenCV."""
    from infrastructure.automation import vision
    matches = vision.find_template(
        vision.load_image(image),
        vision.load_image(template),
        threshold=threshold,
    )
    if not matches:
        _warn("Nenhuma correspondência / No matches")
        raise typer.Exit(1)
    _ok(str(len(matches)) + " match(es)")
    for x, y, score in matches[:10]:
        typer.echo("  ({}, {}) score={:.3f}".format(x, y, score))

@app.command("automate-record")
def automate_record(
    out: str = typer.Option("macro.json", "--out", "-o"),
    duration: float = typer.Option(10.0, "--duration", "-d",
        help="Duração em segundos / Duration in seconds"),
):
    """Grava macro de mouse durante N segundos."""
    import time as _t
    from infrastructure.automation.recorder import Recorder
    rec = Recorder()
    rec.start()
    _info("Gravando por " + str(duration) + "s... / Recording...")
    _t.sleep(duration)
    macro = rec.stop()
    Recorder.save(macro, out)
    _ok("Macro salva / saved: " + out + " (" + str(len(macro.events)) + " eventos)")


@app.command("automate-play")
def automate_play(
    macro: str = typer.Option(..., "--macro", "-m"),
    speed: float = typer.Option(1.0,  "--speed", "-s"),
):
    """Reproduz macro gravado / Replay recorded macro."""
    from infrastructure.automation.recorder import Recorder
    m = Recorder.load(macro)
    _info("Reproduzindo " + str(len(m.events)) + " eventos a " + str(speed) + "x")
    Recorder.play(m, speed=speed)
    _ok("Concluído / Done")




def _disparar_senior(ambiente: str = "producao") -> bool:
    """Dispara o executável do Senior diretamente na rede ou via fallback local."""
    import subprocess
    from pathlib import Path

    eh_homologacao = "homolog" in ambiente.lower()
    pasta_servidor = "Senior_HML" if eh_homologacao else "Senior"
    servidor_host = "SRVVETORH-HML" if eh_homologacao else "SRVVETORH"
    diretorio_senior = r"C:\Senior-hml" if eh_homologacao else r"C:\Senior"
    executavel_rede = f"\\\\{servidor_host}\\{pasta_servidor}\\Iniciar.exe"
    argumentos = f'-SystemModule:VETORH.RONDA -seniordir:"{diretorio_senior}\\"'

    try:
        subprocess.Popen(f'"{executavel_rede}" {argumentos}', shell=True)
        return True
    except Exception:
        pass

    executavel_local = Path(diretorio_senior) / "Vetorh" / "RONDA.EXE"
    if executavel_local.exists():
        try:
            subprocess.Popen([str(executavel_local)], cwd=str(executavel_local.parent))
            return True
        except Exception:
            pass

    return False


def _val(parametro, padrao=None):
    """Extrai o valor real quando a função CLI é chamada diretamente em Python."""
    if hasattr(parametro, "default"):
        return parametro.default
    return parametro if parametro is not None else padrao


def _resolver_template_ambiente(nome_arquivo: str, ambiente: str) -> Path:
    """Resolve o caminho do template priorizando a pasta do ambiente."""
    from pathlib import Path

    ambiente_limpo = "homologacao" if "homolog" in ambiente.lower() else "producao"
    raiz_templates = Path("assets/templates")
    caminho_ambiente = raiz_templates / ambiente_limpo / nome_arquivo
    if caminho_ambiente.exists():
        return caminho_ambiente
    return raiz_templates / nome_arquivo


def _clicar_template_com_auditoria(
    nome_template: str,
    ambiente: str,
    timeout: int,
    confidence: float,
    arquivo_erro: str,
    arquivo_sucesso: str,
) -> None:
    """Localiza e clica em um template visual salvando prints em caso de sucesso ou falha."""
    import time
    from pathlib import Path
    from infrastructure.automation import gui

    ambiente_limpo = "homologacao" if "homolog" in ambiente.lower() else "producao"
    pasta_prints = Path(f"assets/prints/{ambiente_limpo}")
    pasta_prints.mkdir(parents=True, exist_ok=True)

    caminho_template = _resolver_template_ambiente(nome_template, ambiente)
    if not caminho_template.exists():
        _err(f"Template visual '{nome_template}' não encontrado.")
        raise typer.Exit(1)

    _info(f"Localizando '{nome_template}' na tela (timeout: {timeout}s)...")
    posicao = gui.wait_for(str(caminho_template), timeout=float(timeout), confidence=confidence)
    if not posicao:
        try:
            gui.screenshot(save_to=str(pasta_prints / arquivo_erro))
        except Exception:
            pass
        _err(f"Elemento '{nome_template}' não encontrado na tela.")
        raise typer.Exit(1)

    _ok(f"Elemento '{nome_template}' encontrado em {posicao}. Clicando...")
    gui.click(posicao[0], posicao[1])
    time.sleep(1)

    try:
        gui.screenshot(save_to=str(pasta_prints / arquivo_sucesso))
    except Exception:
        pass


def _processar_disparo_emails_lote(
    colaboradores: list,
    obter_pdf_por_matricula,
    pasta_relatorios: Path,
    modo: str,
) -> tuple[int, int]:
    """Executa o envio de e-mails para a lista de colaboradores e gera a planilha de controle."""
    from datetime import datetime
    from schemas.execucao import RegistroExecucaoColaborador, StatusExecucao
    from services.email_service import EmailService
    from services.relatorio_service import RelatorioService

    total_envios = 0
    total_erros = 0
    registros_execucao = []
    momento_execucao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    for colaborador in colaboradores:
        caminho_pdf = obter_pdf_por_matricula(colaborador.matricula)
        registro = RegistroExecucaoColaborador(
            data_execucao=momento_execucao,
            matricula=colaborador.matricula,
            colaborador=colaborador.nome,
            email=colaborador.email,
            status=StatusExecucao.PENDENTE,
            motivo_erro="",
        )

        if not caminho_pdf or not Path(caminho_pdf).exists():
            registro.status = StatusExecucao.ERRO
            registro.motivo_erro = f"Cartão individual {colaborador.matricula}.pdf não encontrado."
            total_erros += 1
            registros_execucao.append(registro)
            _warn(f"Cartão do colaborador {colaborador.nome} (Código: {colaborador.matricula}) não encontrado.")
            continue

        try:
            EmailService.enviar_cartao_ponto(
                destinatario_email=colaborador.email,
                nome_colaborador=colaborador.nome,
                caminho_pdf_anexo=caminho_pdf,
                modo=modo,
            )
            registro.status = StatusExecucao.SUCESSO
            total_envios += 1
            _ok(f"E-mail enviado para: {colaborador.nome} <{colaborador.email}> | Anexo: {Path(caminho_pdf).name}")
        except Exception as erro_envio:
            registro.status = StatusExecucao.ERRO
            registro.motivo_erro = str(erro_envio)
            total_erros += 1
            _err(f"Falha ao enviar e-mail para {colaborador.nome}: {erro_envio}")

        registros_execucao.append(registro)

    try:
        pasta_relatorios.mkdir(parents=True, exist_ok=True)
        caminho_relatorio = RelatorioService().gerar_relatorio_execucao(
            registros=registros_execucao,
            pasta_destino=pasta_relatorios,
            momento_execucao=datetime.now(),
        )
        _ok(f"Relatório de Controle gerado: {caminho_relatorio}")
    except Exception as erro_relatorio:
        _warn(f"Aviso ao gerar relatório de controle: {erro_relatorio}")

    return total_envios, total_erros


@app.command("senior-open")
def senior_open(
    ambiente: str = typer.Option("producao", "--ambiente", "-a", help="Ambiente: homologacao ou producao"),
):
    """Abre o sistema Senior (Controle de Ponto e Refeitório)."""
    ambiente = _val(ambiente, "producao")
    _sec(f"Abertura do Senior ({ambiente})")
    if _disparar_senior(ambiente):
        _ok("Executável do Senior disparado com sucesso.")
    else:
        _err("Não foi possível disparar o Senior automaticamente.")
        raise typer.Exit(1)


@app.command("senior-login")
def senior_login(
    usuario: str = typer.Option("", "--user", "-u", help="Usuário do Senior (busca do .env se omitido)"),
    senha: str = typer.Option("", "--password", "-p", help="Senha do Senior (busca do .env se omitido)"),
    abrir: bool = typer.Option(True, "--abrir/--no-abrir", help="Abrir o Senior antes da autenticação"),
    ambiente: str = typer.Option("producao", "--ambiente", "-a", help="Ambiente: homologacao ou producao"),
    timeout: int = typer.Option(60, "--timeout", "-t", help="Timeout para aguardar a tela de login (segundos)"),
    confidence: float = typer.Option(0.75, "--confidence", "-c", help="Nível de confiança visual (0.1 a 1.0)"),
):
    """Realiza o login no sistema Senior por imagem (OpenCV + PyAutoGUI)."""
    import time
    import pyperclip
    from pathlib import Path
    from core.config import settings
    from infrastructure.automation import gui

    usuario = _val(usuario, "")
    senha = _val(senha, "")
    abrir = _val(abrir, True)
    ambiente = _val(ambiente, "producao")
    timeout = _val(timeout, 60)
    confidence = _val(confidence, 0.75)

    _sec("Autenticação Senior Desktop (OpenCV + PyAutoGUI)")

    if abrir:
        _info(f"Iniciando Senior ({ambiente})...")
        if _disparar_senior(ambiente):
            _ok("Processo disparado. Aguardando interface...")
            for _ in range(8):
                time.sleep(1)
                gui.focar_senior_geral()
        else:
            _warn("Não foi possível abrir pelo atalho. Prosseguindo para detecção visual...")
    else:
        gui.focar_senior_geral()

    usuario_final = (usuario or settings.SENIOR_LOGIN or "").strip().lower()
    senha_final = senha or settings.SENIOR_PASSWORD
    if not usuario_final:
        _err("Usuário não configurado! Passe --user ou defina SENIOR_LOGIN no .env")
        raise typer.Exit(1)

    ambiente_limpo = "homologacao" if "homolog" in ambiente.lower() else "producao"
    pasta_prints = Path(f"assets/prints/{ambiente_limpo}")
    pasta_prints.mkdir(parents=True, exist_ok=True)

    template_autenticar = _resolver_template_ambiente("botao_autenticar.png", ambiente)
    if not template_autenticar.exists():
        _err("Template visual 'botao_autenticar.png' não encontrado.")
        raise typer.Exit(1)

    template_modulo = _resolver_template_ambiente("icone_modulo.png", ambiente)
    if template_modulo.exists():
        posicao_modulo = gui.wait_for(str(template_modulo), timeout=4, confidence=0.75)
        if posicao_modulo:
            gui.click(posicao_modulo[0], posicao_modulo[1])
            time.sleep(2)

    _info(f"Localizando tela de autenticação (timeout: {timeout}s)...")
    posicao_botao = None
    inicio_login = time.time()
    while time.time() - inicio_login < float(timeout):
        posicao_botao = gui.locate_center_on_screen(str(template_autenticar), confidence=confidence)
        if posicao_botao:
            break
        gui.focar_senior_geral()
        time.sleep(1.2)

    if not posicao_botao:
        try:
            gui.screenshot(save_to=str(pasta_prints / "erro_login_nao_encontrado.png"))
        except Exception:
            pass
        _err(f"Botão 'Autenticar' não encontrado após {timeout}s.")
        raise typer.Exit(1)

    # Campo de usuário fica 93px acima do botão Autenticar em 1080p;
    # pyperclip evita perda de maiúsculas durante digitação em sessões RDP.
    gui.click(posicao_botao[0], posicao_botao[1] - 93)
    time.sleep(0.3)
    gui.hotkey("ctrl", "a")
    gui.press("backspace")
    pyperclip.copy(usuario_final)
    gui.hotkey("ctrl", "v")
    _ok(f"Usuário '{usuario_final}' inserido.")

    gui.press("tab")
    time.sleep(0.3)
    gui.hotkey("ctrl", "a")
    gui.press("backspace")
    pyperclip.copy(senha_final)
    gui.hotkey("ctrl", "v")
    time.sleep(0.2)
    pyperclip.copy("")
    _ok("Senha inserida.")

    time.sleep(0.5)
    gui.click(posicao_botao[0], posicao_botao[1])
    time.sleep(1)

    _info("Aguardando carregamento do sistema Senior...")
    for indice in range(30):
        time.sleep(1)
        if not gui.locate_on_screen(str(template_autenticar), confidence=0.65):
            _ok(f"Autenticação aceita em ~{indice + 1}s.")
            break
    else:
        _warn("Tela de login ainda presente após 30s. Verifique as credenciais.")

    time.sleep(2)
    if template_modulo.exists():
        for _ in range(15):
            gui.focar_senior_geral()
            posicao_modulo = gui.locate_center_on_screen(str(template_modulo), confidence=0.68)
            if posicao_modulo:
                gui.click(posicao_modulo[0], posicao_modulo[1])
                time.sleep(3)
                break
            time.sleep(1)

    time.sleep(2)
    try:
        gui.screenshot(save_to=str(pasta_prints / "02_apos_login.png"))
    except Exception:
        pass
    _ok("Login e abertura do módulo executados com sucesso!")


@app.command("senior-calculos")
def senior_calculos(
    ambiente: str = typer.Option("producao", "--ambiente", "-a", help="Ambiente: homologacao ou producao"),
    timeout: int = typer.Option(10, "--timeout", "-t", help="Timeout para localizar a aba Cálculos"),
    confidence: float = typer.Option(0.75, "--confidence", "-c", help="Confiança da detecção visual"),
):
    """Localiza e clica na aba 'Cálculos' do Senior Desktop."""
    _sec(f"Navegação Senior: Menu Cálculos ({ambiente})")
    _clicar_template_com_auditoria(
        nome_template="menu_calculos.png",
        ambiente=ambiente,
        timeout=timeout,
        confidence=confidence,
        arquivo_erro="erro_menu_calculos_nao_encontrado.png",
        arquivo_sucesso="03_apos_clicar_calculos.png",
    )
    _ok("Clique no menu 'Cálculos' realizado com sucesso!")


@app.command("senior-click")
def senior_click(
    template: str = typer.Argument(..., help="Nome do template PNG (ex: menu_apuracao, menu_calculos)"),
    ambiente: str = typer.Option("producao", "--ambiente", "-a", help="Ambiente: homologacao ou producao"),
    timeout: int = typer.Option(10, "--timeout", "-t", help="Timeout de localização"),
    confidence: float = typer.Option(0.75, "--confidence", "-c", help="Nível de confiança visual"),
):
    """Localiza e clica em qualquer template PNG cadastrado."""
    nome_arquivo = template if template.endswith(".png") else f"{template}.png"
    _sec(f"Senior Click: {nome_arquivo} ({ambiente})")
    _clicar_template_com_auditoria(
        nome_template=nome_arquivo,
        ambiente=ambiente,
        timeout=timeout,
        confidence=confidence,
        arquivo_erro=f"erro_{template}_nao_encontrado.png",
        arquivo_sucesso=f"apos_clique_{template}.png",
    )
    _ok(f"Clique em '{nome_arquivo}' executado com sucesso!")


@app.command("senior-menu-cartao")
def senior_menu_cartao(
    ambiente: str = typer.Option("producao", "--ambiente", "-a", help="Ambiente: homologacao ou producao"),
    timeout_passo: int = typer.Option(20, "--timeout", "-t", help="Timeout para cada clique de menu"),
    confidence: float = typer.Option(0.70, "--confidence", "-c", help="Nível de confiança visual"),
):
    """Navega pelos menus: Cálculos -> Apuração -> Listar -> Cartão Ponto."""
    import time
    from pathlib import Path
    from infrastructure.automation import gui
    from services.senior_service import SeniorService

    _sec(f"Navegação Senior: Menu Completo Cartão Ponto ({ambiente})")
    ambiente_limpo = "homologacao" if "homolog" in ambiente.lower() else "producao"
    pasta_prints = Path(f"assets/prints/{ambiente_limpo}")
    pasta_prints.mkdir(parents=True, exist_ok=True)

    servico = SeniorService(ambiente=ambiente)
    servico.confidence = confidence
    servico.garantir_menu_principal_pronto(timeout=float(timeout_passo))

    etapas_menu = (
        ("menu_calculos.png", "Cálculos"),
        ("menu_apuracao.png", "Apuração"),
        ("menu_listar.png", "Listar"),
        ("menu_cartao_ponto.png", "Cartão Ponto"),
    )

    for arquivo_tpl, descricao in etapas_menu:
        caminho_template = servico._obter_template(arquivo_tpl)
        if not caminho_template:
            _err(f"Template visual '{arquivo_tpl}' não encontrado.")
            raise typer.Exit(1)

        posicao = gui.wait_for(str(caminho_template), timeout=float(timeout_passo), confidence=confidence)
        if not posicao:
            servico.tratar_obstaculos_conhecidos()
            posicao = gui.wait_for(str(caminho_template), timeout=5.0, confidence=confidence)

        if not posicao:
            try:
                gui.screenshot(save_to=str(pasta_prints / f"erro_menu_{arquivo_tpl}"))
            except Exception:
                pass
            _err(f"Menu '{descricao}' não encontrado na tela.")
            raise typer.Exit(1)

        _ok(f"Menu '{descricao}' encontrado em {posicao}. Clicando...")
        gui.click(posicao[0], posicao[1])
        time.sleep(0.35)

    time.sleep(2)
    try:
        gui.screenshot(save_to=str(pasta_prints / "04_tela_relatorio_702.png"))
    except Exception:
        pass
    _ok("Navegação completa até o Cartão Ponto realizada com sucesso!")


@app.command("senior-selecionar-702")
def senior_selecionar_702(
    ambiente: str = typer.Option("producao", "--ambiente", "-a", help="Ambiente: homologacao ou producao"),
    timeout: int = typer.Option(15, "--timeout", "-t", help="Timeout para aguardar a janela de Modelos"),
):
    """Passo 5: Seleciona o modelo 702 ('UnimedVA - Cartão Ponto Portal')."""
    from services.senior_service import SeniorService

    ambiente = _val(ambiente, "producao")
    timeout = _val(timeout, 15)
    _sec(f"Passo 5: Seleção de Relatório 702 ({ambiente})")
    servico = SeniorService(ambiente=ambiente)
    if servico.selecionar_relatorio_702(timeout_janela=timeout):
        _ok("Opção 702 selecionada com sucesso!")
    else:
        _err("Falha ao selecionar o relatório 702.")
        raise typer.Exit(1)


@app.command("senior-selecionar-001")
def senior_selecionar_001(
    ambiente: str = typer.Option("producao", "--ambiente", "-a", help="Ambiente: homologacao ou producao"),
    timeout: int = typer.Option(15, "--timeout", "-t", help="Timeout para aguardar a janela de Modelos"),
):
    """Passo 5: Seleciona o modelo 001 ('Cartão Ponto Simples')."""
    from services.senior_service import SeniorService

    ambiente = _val(ambiente, "producao")
    timeout = _val(timeout, 15)
    _sec(f"Passo 5: Seleção de Relatório 001 ({ambiente})")
    servico = SeniorService(ambiente=ambiente)
    if servico.selecionar_relatorio_001(timeout_janela=timeout):
        _ok("Opção 001 ('Cartão Ponto Simples') selecionada com sucesso!")
    else:
        _err("Falha ao selecionar o relatório 001.")
        raise typer.Exit(1)


@app.command("senior-valores-entrada")
def senior_valores_entrada(
    data_inicial: str = typer.Option("", "--data-inicial", "-i", help="Data inicial dd/mm/aaaa"),
    data_final: str = typer.Option("", "--data-final", "-f", help="Data final dd/mm/aaaa"),
    ambiente: str = typer.Option("producao", "--ambiente", "-a", help="Ambiente: homologacao ou producao"),
    timeout: int = typer.Option(15, "--timeout", "-t", help="Timeout para aguardar o modal"),
):
    """Passo 6: Preenche Data Inicial e Final no modal Valores de Entrada e clica em Ok."""
    from services.senior_service import SeniorService

    data_inicial = _val(data_inicial, "")
    data_final = _val(data_final, "")
    ambiente = _val(ambiente, "producao")
    timeout = _val(timeout, 15)

    _sec(f"Passo 6: Preenchimento de Valores de Entrada ({ambiente})")
    servico = SeniorService(ambiente=ambiente)
    if not data_inicial or not data_final:
        data_inicial, data_final = servico.calcular_periodo_pdd()

    _info(f"Período: {data_inicial} até {data_final}")
    if servico.preencher_datas_e_gerar(data_inicial=data_inicial, data_final=data_final, timeout_janela=timeout):
        _ok("Passo 6 executado com sucesso!")
    else:
        _err("Falha ao preencher Valores de Entrada.")
        raise typer.Exit(1)


@app.command("senior-aguardar-salvar")
def senior_aguardar_salvar(
    destino: str = typer.Option("", "--destino", "-d", help="Caminho do PDF destino"),
    ambiente: str = typer.Option("producao", "--ambiente", "-a", help="Ambiente: homologacao ou producao"),
    timeout: int = typer.Option(1200, "--timeout", "-t", help="Timeout em segundos para aguardar o relatório"),
    modelo: str = typer.Option("702", "--modelo", "-mod", help="Modelo do relatório: 702 ou 001"),
):
    """Passo 7: Aguarda a visualização do relatório, clica no disquete e salva na rede."""
    from services.senior_service import SeniorService

    destino = _val(destino, "")
    ambiente = _val(ambiente, "producao")
    timeout = _val(timeout, 1200)
    modelo_codigo = str(_val(modelo, "702")).strip().zfill(3)

    _sec(f"Passo 7: Aguardo e Salvamento do Relatório Modelo {modelo_codigo} ({ambiente})")
    servico = SeniorService(ambiente=ambiente)
    caminho_final = servico.aguardar_relatorio_e_salvar(
        caminho_destino_pdf=Path(destino) if destino else None,
        timeout_segundos=timeout,
        modelo=modelo_codigo,
    )
    if caminho_final:
        _ok(f"Arquivo consolidado salvo em: {caminho_final}")
    else:
        _err("Falha ao salvar relatório consolidado.")
        raise typer.Exit(1)


@app.command("senior-fluxo")
def senior_fluxo(
    usuario: str = typer.Option("", "--user", "-u", help="Usuário do Senior (busca do .env se omitido)"),
    senha: str = typer.Option("", "--password", "-p", help="Senha do Senior (busca do .env se omitido)"),
    abrir: bool = typer.Option(True, "--abrir/--no-abrir", help="Abrir o Senior antes da autenticação"),
    ambiente: str = typer.Option("producao", "--ambiente", "-a", help="Ambiente: homologacao ou producao"),
    timeout: int = typer.Option(60, "--timeout", "-t", help="Timeout para aguardar telas e elementos"),
    confidence: float = typer.Option(0.70, "--confidence", "-c", help="Nível de confiança visual"),
    selecionar_702: bool = typer.Option(True, "--selecionar-702/--sem-702", help="Executar o Passo 5 (Seleção do Modelo)"),
    modelo: str = typer.Option("702", "--modelo", "-mod", help="Modelo do relatório: 702 ou 001"),
    enviar_emails: bool = typer.Option(True, "--enviar-emails/--sem-emails", help="Enviar os e-mails após separar os PDFs"),
):
    """Executa o fluxo completo: Login -> Menus -> Modelo -> Datas -> Salvar PDF -> Fechar Senior -> Separar PDFs -> E-mails."""
    import time
    from services.colaboradores_service import ColaboradoresService
    from services.pdf_splitter_service import PdfSplitterService
    from services.senior_service import SeniorService

    usuario = _val(usuario, "")
    senha = _val(senha, "")
    abrir = _val(abrir, True)
    ambiente = _val(ambiente, "producao")
    timeout = _val(timeout, 60)
    confidence = _val(confidence, 0.70)
    selecionar_702 = _val(selecionar_702, True)
    modelo_codigo = str(_val(modelo, "702")).strip().zfill(3)
    enviar_emails = _val(enviar_emails, True)

    _sec(f"Fluxo Geral Senior: Modelo {modelo_codigo} ({ambiente})")

    servico = SeniorService(ambiente=ambiente)
    try:
        senior_login(
            usuario=usuario,
            senha=senha,
            abrir=abrir,
            ambiente=ambiente,
            timeout=timeout,
            confidence=confidence,
        )
        time.sleep(1.2)
        senior_menu_cartao(ambiente=ambiente, timeout_passo=timeout, confidence=confidence)

        if not selecionar_702:
            _ok("Fluxo geral executado com sucesso!")
            return

        selecionou = (
            servico.selecionar_relatorio_001(timeout_janela=15)
            if modelo_codigo == "001"
            else servico.selecionar_relatorio_702(timeout_janela=15)
        )
        if not selecionou:
            _warn(f"Não foi possível selecionar o modelo {modelo_codigo}.")
            return
        _ok(f"Modelo {modelo_codigo} selecionado!")

        data_ini_calc, data_fim_calc = servico.calcular_periodo_pdd()
        if not servico.preencher_datas_e_gerar(data_inicial=data_ini_calc, data_final=data_fim_calc, timeout_janela=15):
            _warn("Não foi possível preencher os Valores de Entrada.")
            return
        _ok(f"Valores de Entrada preenchidos: {data_ini_calc} até {data_fim_calc}")

        arquivo_salvo = servico.aguardar_relatorio_e_salvar(modelo=modelo_codigo)
        if not arquivo_salvo:
            _warn("Relatório consolidado não foi salvo automaticamente.")
            return
        _ok(f"Relatório consolidado salvo em: {arquivo_salvo}")

        if servico.encerrar_senior():
            _ok("Senior Desktop encerrado via PID após salvamento do PDF.")

        pasta_individuais = arquivo_salvo.parent / "individuais"
        pasta_individuais.mkdir(parents=True, exist_ok=True)
        mapa_individuais = PdfSplitterService.dividir_cartoes_ponto(
            caminho_consolidado=arquivo_salvo,
            pasta_destino=pasta_individuais,
        )
        _ok(f"{len(mapa_individuais)} cartões individuais gerados em: {pasta_individuais}")

        if not enviar_emails:
            _info("Etapa 7 ignorada (--sem-emails): fluxo encerrado após separação dos PDFs.")
            _ok("Fluxo geral executado com sucesso!")
            return

        colaboradores = ColaboradoresService.carregar_colaboradores()
        total_envios, total_erros = _processar_disparo_emails_lote(
            colaboradores=colaboradores,
            obter_pdf_por_matricula=lambda matricula: mapa_individuais.get(matricula),
            pasta_relatorios=arquivo_salvo.parent / "relatorios",
            modo="04",
        )
        _ok(f"Etapa 7 concluída! {total_envios} e-mails enviados ({total_erros} erros).")
        _ok("Fluxo geral executado com sucesso!")
    finally:
        if servico.obter_pids_senior():
            servico.encerrar_senior()


@app.command("senior-fluxo-001")
def senior_fluxo_001(
    usuario: str = typer.Option("", "--user", "-u", help="Usuário do Senior (busca do .env se omitido)"),
    senha: str = typer.Option("", "--password", "-p", help="Senha do Senior (busca do .env se omitido)"),
    abrir: bool = typer.Option(True, "--abrir/--no-abrir", help="Abrir o Senior antes da autenticação"),
    ambiente: str = typer.Option("producao", "--ambiente", "-a", help="Ambiente: homologacao ou producao"),
    timeout: int = typer.Option(60, "--timeout", "-t", help="Timeout para aguardar telas e elementos"),
    confidence: float = typer.Option(0.70, "--confidence", "-c", help="Nível de confiança visual"),
    enviar_emails: bool = typer.Option(True, "--enviar-emails/--sem-emails", help="Enviar os e-mails após separar os PDFs"),
):
    """Executa o fluxo completo ponta a ponta utilizando o Modelo 001 ('Cartão Ponto Simples')."""
    senior_fluxo(
        usuario=usuario,
        senha=senha,
        abrir=abrir,
        ambiente=ambiente,
        timeout=timeout,
        confidence=confidence,
        selecionar_702=True,
        modelo="001",
        enviar_emails=enviar_emails,
    )


@app.command("senior-extrair")
def senior_extrair(
    usuario: str = typer.Option("", "--user", "-u", help="Usuário do Senior (busca do .env se omitido)"),
    senha: str = typer.Option("", "--password", "-p", help="Senha do Senior (busca do .env se omitido)"),
    abrir: bool = typer.Option(True, "--abrir/--no-abrir", help="Abrir o Senior antes da autenticação"),
    ambiente: str = typer.Option("producao", "--ambiente", "-a", help="Ambiente: homologacao ou producao"),
    timeout: int = typer.Option(60, "--timeout", "-t", help="Timeout para aguardar telas e elementos"),
    confidence: float = typer.Option(0.70, "--confidence", "-c", help="Nível de confiança visual"),
    modelo: str = typer.Option("001", "--modelo", "-mod", help="Modelo do relatório: 001 ou 702"),
):
    """Executa o fluxo até separar os PDFs individuais (Fecha o Senior via PID e NÃO envia e-mails)."""
    senior_fluxo(
        usuario=usuario,
        senha=senha,
        abrir=abrir,
        ambiente=ambiente,
        timeout=timeout,
        confidence=confidence,
        selecionar_702=True,
        modelo=modelo,
        enviar_emails=False,
    )


@app.command("senior-fechar")
def senior_fechar():
    """Encerra com segurança todos os processos ativos do Senior Desktop via PID."""
    from services.senior_service import SeniorService

    servico = SeniorService()
    _sec("Encerramento do Senior Desktop (via PID)")
    pids = servico.obter_pids_senior()
    if not pids:
        _warn("Nenhum processo ativo do Senior Desktop foi encontrado na máquina.")
        return
    _info(f"Processos localizados com PID(s): {pids}")
    if servico.encerrar_senior():
        _ok(f"Processo(s) {pids} finalizado(s) com sucesso.")
    else:
        _err("Não foi possível finalizar os processos do Senior.")


@app.command("senior-separar-pdfs")
def senior_separar_pdfs(
    consolidado: str = typer.Option("", "--consolidado", "-c", help="Caminho do arquivo consolidado PDF"),
    destino: str = typer.Option("", "--destino", "-d", help="Pasta de destino dos PDFs individuais"),
    timeout: int = typer.Option(1200, "--timeout", "-t", help="Timeout para aguardar o arquivo estabilizar"),
    modelo: str = typer.Option("702", "--modelo", "-mod", help="Modelo do relatório: 702 ou 001"),
):
    """Passo 8: Divide o PDF consolidado em cartões individuais nomeados com o código do empregado."""
    from datetime import datetime
    from core.config import settings
    from services.pdf_splitter_service import PdfSplitterService
    from services.senior_service import SeniorService

    _sec("Passo 8: Separação de Cartões Individuais por Código")
    pasta_base = Path(settings.REDE_PASTA_CONSOLIDADO)
    data_hoje = datetime.now().strftime("%d%m%Y")
    pasta_dia = pasta_base / data_hoje
    modelo_codigo = str(_val(modelo, "702")).strip().zfill(3)

    if consolidado:
        caminho_pdf = Path(consolidado)
    else:
        caminho_pdf = None
        if pasta_dia.exists():
            servico = SeniorService()
            caminho_pdf = servico.aguardar_arquivo_pdf_estabilizado(
                pasta=pasta_dia,
                nome_esperado=f"HRCP{modelo_codigo}_{data_hoje}.pdf",
                timeout_segundos=timeout,
            )

        if not caminho_pdf or not caminho_pdf.exists():
            arquivos_encontrados = sorted(
                pasta_base.glob("**/HRCP*.pdf"),
                key=lambda arquivo: arquivo.stat().st_mtime,
                reverse=True,
            )
            if not arquivos_encontrados:
                _err(f"Nenhum arquivo consolidado PDF encontrado em: {pasta_dia} ou {pasta_base}")
                raise typer.Exit(1)
            caminho_pdf = arquivos_encontrados[0]

    pasta_destino = Path(destino) if destino else (caminho_pdf.parent / "individuais")
    pasta_destino.mkdir(parents=True, exist_ok=True)

    mapa_individuais = PdfSplitterService.dividir_cartoes_ponto(caminho_pdf, pasta_destino)
    _ok(f"Separação concluída! Total de {len(mapa_individuais)} arquivos gerados em {pasta_destino}.")
    for matricula_item, caminho_item in list(mapa_individuais.items())[:5]:
        _info(f" - Código {matricula_item} -> {caminho_item.name}")


@app.command("senior-enviar-emails")
def senior_enviar_emails(
    modo: str = typer.Option("04", "--modo", "-m", help="Modo do PDD: 04, 20 ou 30"),
    pasta_individuais: str = typer.Option("", "--individuais", "-i", help="Pasta contendo os PDFs individuais"),
    planilha: str = typer.Option("", "--planilha", "-p", help="Caminho da planilha de colaboradores"),
    matricula: str = typer.Option("", "--matricula", "-mat", help="Filtra por matrícula específica para teste"),
):
    """Passo 10: Lê a planilha de colaboradores e envia os e-mails com os cartões individuais anexados."""
    from datetime import datetime
    from core.config import settings
    from services.colaboradores_service import ColaboradoresService

    _sec(f"Passo 10: Disparo de E-mails aos Colaboradores (Modo Dia {modo})")
    data_hoje = datetime.now().strftime("%d%m%Y")
    pasta_base = Path(settings.REDE_PASTA_CONSOLIDADO)
    pasta_dia = pasta_base / data_hoje

    if pasta_individuais:
        pasta_indiv = Path(pasta_individuais)
    elif (pasta_dia / "individuais").exists():
        pasta_indiv = pasta_dia / "individuais"
    else:
        pasta_indiv = Path(settings.REDE_PASTA_INDIVIDUAIS)

    if not pasta_indiv.exists() and Path("data/individuais").exists():
        pasta_indiv = Path("data/individuais")

    pasta_relatorios = (pasta_dia / "relatorios") if pasta_dia.exists() else Path(settings.REDE_PASTA_RELATORIOS)
    try:
        pasta_relatorios.mkdir(parents=True, exist_ok=True)
    except Exception:
        _warn(f"Pasta de rede inacessível ({pasta_relatorios}). Usando 'data/relatorios'...")
        pasta_relatorios = Path("data/relatorios")
        pasta_relatorios.mkdir(parents=True, exist_ok=True)

    arquivo_planilha = _val(planilha, "") or settings.PLANILHA_COLABORADORES_PATH
    colaboradores = ColaboradoresService.carregar_colaboradores(arquivo_planilha)

    filtro_matricula = _val(matricula, "").strip()
    if filtro_matricula:
        colaboradores = [
            colab for colab in colaboradores if str(colab.matricula).strip() == filtro_matricula
        ]
        _info(f"Filtro aplicado: '{filtro_matricula}' ({len(colaboradores)} colaborador).")

    def _buscar_pdf_individual(codigo_matricula: str):
        caminho_padrao = pasta_indiv / f"{codigo_matricula}.pdf"
        if caminho_padrao.exists():
            return caminho_padrao
        caminho_alternativo = pasta_indiv / f"Cartao_Ponto_{codigo_matricula}.pdf"
        return caminho_alternativo if caminho_alternativo.exists() else None

    total_envios, total_erros = _processar_disparo_emails_lote(
        colaboradores=colaboradores,
        obter_pdf_por_matricula=_buscar_pdf_individual,
        pasta_relatorios=pasta_relatorios,
        modo=modo,
    )
    _ok(f"Disparo concluído: {total_envios} e-mails enviados com sucesso ({total_erros} falhas).")


if __name__ == "__main__":
    app()
