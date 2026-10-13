---
id: ADR-0001
title: "Typer + Rich, gestionado con uv"
status: accepted
date: 2026-10-13
supersedes:
---

# ADR-0001 — Typer + Rich, gestionado con uv

## Contexto
Se necesita una CLI con grupos y subcomandos, ayuda autogenerada, salida legible y un entorno
reproducible en WSL y en CI.

## Decisión
- **Typer** como framework (subcomandos a partir de type hints, autocompletado); **Rich** para
  tablas y colores. Alternativa descartada: Click puro (más código para lo mismo).
- **pydantic-settings** para leer y validar el `.env`.
- **uv** para dependencias, entorno, ejecución y empaquetado (`uv_build`, `uv.lock` versionado).

## Consecuencias
- El entry point es `campaigns = "campaigns_cli.main:app"`; se ejecuta con `uv run campaigns`.
- El `.venv` debe ir fuera de OneDrive (`UV_PROJECT_ENVIRONMENT`) por rendimiento.
- Origen: [T-001](../../backlog/tasks/T-001-esqueleto-uv.md).
