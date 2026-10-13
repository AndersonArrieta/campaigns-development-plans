# T-10 — Documentación y CI

- **Grupo:** —
- **Secciones del plan:** §7, §11
- **Depende de:** T-01 a T-09

## Objetivo

Dejar la CLI lista para que otra persona del equipo la instale y la use sin ayuda, y automatizar lint y pruebas en cada cambio.

## Archivos

| Archivo | Cambio |
|---|---|
| `README.md` | Guía de instalación, configuración y uso. |
| `.env.example` | Revisión final con los nombres reales de dev (sin secretos). |
| `.github/workflows/campaigns-cli.yml` o `.gitlab-ci.yml` / `azure-pipelines.yml` | Pipeline de lint y pruebas (según la plataforma del repo, D-6). |
| `pyproject.toml` | Umbral de cobertura (`--cov-fail-under=80` sobre `services/`). |

## Pasos

1. `README.md` con estas secciones:
   - **Requisitos:** uv, credenciales AWS por perfil o SSO.
   - **Instalación:** `uv sync`; opcional `uv tool install --editable .`.
   - **Configuración:** copiar `.env.example` a `.env`, tabla de variables, uso de `--env-file .env.qa`.
   - **Comandos:** un ejemplo por grupo (`config`, `csv`, `s3`, `lambda`, `dynamo`, `logs`, `trace`).
   - **Receta típica:** `csv generate` → `trace run` → `logs search` → `dynamo purge`.
   - **Protecciones:** qué está bloqueado en prod y cómo funciona `--yes`.
   - **Códigos de salida.**
   - **Desarrollo:** comandos de prueba, lint y tipado; cómo agregar un nuevo grupo de comandos (`commands/` + `services/` + registro en `main.py`).
2. Autocompletado: documentar `campaigns --install-completion` (Typer).
3. Pipeline:
   ```yaml
   - uses: astral-sh/setup-uv@v6
   - run: uv sync --locked
   - run: uv run ruff check . && uv run ruff format --check .
   - run: uv run mypy src
   - run: uv run pytest --cov=campaigns_cli --cov-fail-under=80
   ```
   Sin credenciales AWS en el pipeline: las pruebas usan moto y `Stubber`.
4. Revisar los criterios de aceptación del plan (§11) y marcarlos.

## Pruebas

- Seguir el README desde cero en una máquina (o contenedor) limpia y ejecutar `campaigns config check` y `campaigns csv generate`.
- El pipeline corre en verde en una rama de prueba.

## Criterios de terminado

- [ ] README probado por alguien distinto a quien desarrolló la CLI.
- [ ] Pipeline en verde con cobertura ≥ 80 % en `services/`.
- [ ] Criterios de aceptación §11 del plan verificados.
- [ ] Commit (lo hace el desarrollador).
