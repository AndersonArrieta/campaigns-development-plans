---
title: "Ready queue (modo agente)"
type: dashboard
---

# 🤖 Ready queue

Cola de ejecución del agente: tareas **desbloqueadas** (todas sus `depends_on` en `done`)
que aún no están hechas, ordenadas por prioridad. Este es el driver del flujo — no el sprint.

> Requiere el plugin **Dataview** (usa `dataviewjs` para calcular la readiness sobre el grafo).

## ▶️ Siguiente a ejecutar (desbloqueadas)
```dataviewjs
const pages = dv.pages('"backlog/tasks" or "backlog/bugs"');
const byId = {};
for (const p of pages) byId[p.id] = p;
const isDone = (id) => byId[id] && byId[id].status === "done";
const prioRank = { P0: 0, P1: 1, P2: 2, P3: 3 };

const ready = pages
  .where(p => p.status !== "done" && p.status !== "doing"
              && (p.depends_on ?? []).every(isDone))
  .sort(p => (prioRank[p.priority] ?? 9) + "-" + p.id);

dv.table(
  ["Tarea", "Prioridad", "Estimación", "Epic"],
  ready.map(p => [p.file.link, p.priority, p.estimate, p.epic])
);
```

## ⏳ Bloqueadas (esperando dependencias)
```dataviewjs
const pages = dv.pages('"backlog/tasks" or "backlog/bugs"');
const byId = {};
for (const p of pages) byId[p.id] = p;
const isDone = (id) => byId[id] && byId[id].status === "done";

const blocked = pages
  .where(p => p.status !== "done" && p.status !== "doing"
              && !(p.depends_on ?? []).every(isDone))
  .sort(p => p.id);

dv.table(
  ["Tarea", "Prioridad", "Falta que terminen"],
  blocked.map(p => [
    p.file.link, p.priority,
    (p.depends_on ?? []).filter(d => !isDone(d)).join(", ")
  ])
);
```

## 🟠 En curso
```dataview
TABLE priority, estimate, epic
FROM "backlog/tasks" OR "backlog/bugs"
WHERE status = "doing"
SORT id ASC
```
