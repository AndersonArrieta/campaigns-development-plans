---
id: ADR-0007
title: "Código en campaigns-cli/ dentro del repo de planes"
status: accepted
date: 2026-10-13
supersedes:
---

# ADR-0007 — Código en campaigns-cli/ dentro del repo de planes

## Contexto
La CLI podía vivir en un repo propio o junto a los planes de campañas.

## Decisión
Vive en `campaigns-cli/` dentro de `AndersonArrieta/campaigns-development-plans` (GitHub), con su
propio `pyproject.toml`, documentación (`docs/`) y backlog (`backlog/`).

## Consecuencias
- El CI es GitHub Actions, con un workflow en la raíz del repo filtrado a `campaigns-cli/**` y
  `working-directory: campaigns-cli` ([T-014](../../backlog/tasks/T-014-ci-github-actions.md)).
- Moverla a un repo propio más adelante requiere un ADR que reemplace a este.
