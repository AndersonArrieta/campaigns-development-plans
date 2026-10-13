# T-01 — Esqueleto del proyecto con uv

- **Grupo:** —
- **Secciones del plan:** §3, §4, §7
- **Depende de:** —

## Objetivo

Crear el proyecto `campaigns-cli` gestionado con uv, con layout `src/`, el entry point `campaigns` y la app Typer raíz respondiendo a `--help`.

## Archivos

| Archivo | Cambio |
|---|---|
| `pyproject.toml` | Metadatos, dependencias, `[project.scripts]`, configuración de `ruff`, `mypy` y `pytest`. |
| `.python-version` | `3.12`. |
| `.gitignore` | `.venv/`, `__pycache__/`, `.pytest_cache/`, `.coverage`, `htmlcov/`, `.env`, `.env.*`, `!.env.example`. |
| `.env.example` | Plantilla vacía (se completa en la T-02). |
| `src/campaigns_cli/__init__.py` | `__version__`. |
| `src/campaigns_cli/main.py` | App Typer raíz con callback y comando `version`. |
| `src/campaigns_cli/commands/__init__.py`, `src/campaigns_cli/services/__init__.py` | Paquetes vacíos. |
| `tests/test_cli.py` | Prueba de humo con `CliRunner`. |

## Pasos

1. Inicializar el proyecto dentro de `campaigns-cli/`:
   ```bash
   uv init --package --name campaigns-cli --python 3.12 .
   uv add typer rich boto3 pydantic-settings
   uv add --dev pytest pytest-cov "moto[s3,dynamodb,logs]" ruff mypy \
       "boto3-stubs[s3,lambda,dynamodb,logs,sts]"
   ```
2. Declarar el entry point en `pyproject.toml`:
   ```toml
   [project.scripts]
   campaigns = "campaigns_cli.main:app"
   ```
3. Crear la app raíz en `main.py`:
   ```python
   import typer

   from campaigns_cli import __version__

   app = typer.Typer(
       name="campaigns",
       help="Pruebas sobre los recursos AWS del flujo de campañas.",
       no_args_is_help=True,
   )


   @app.command()
   def version() -> None:
       """Muestra la versión de la CLI."""
       typer.echo(__version__)
   ```
4. Configurar herramientas en `pyproject.toml`:
   ```toml
   [tool.ruff]
   line-length = 100
   target-version = "py312"

   [tool.ruff.lint]
   select = ["E", "F", "I", "B", "UP", "SIM"]

   [tool.mypy]
   strict = true
   packages = ["campaigns_cli"]

   [tool.pytest.ini_options]
   testpaths = ["tests"]
   ```
5. Ejecutar `uv sync` y confirmar que se genera `uv.lock` (se versiona).

## Pruebas

- `test_cli.py`: `CliRunner().invoke(app, ["--help"])` → exit code 0 y el texto de ayuda.
- `test_cli.py`: `invoke(app, ["version"])` → imprime `__version__`.

## Criterios de terminado

- [ ] `uv sync && uv run campaigns --help` funciona en una máquina limpia.
- [ ] `uv run pytest`, `uv run ruff check .` y `uv run mypy src` en verde.
- [ ] `uv.lock` versionado; `.env` ignorado por git.
- [ ] Commit (lo hace el desarrollador).
