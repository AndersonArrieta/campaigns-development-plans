---
title: "Tablero (Kanban vivo)"
type: dashboard
---

# 🗂️ Tablero

> Se genera solo desde el frontmatter de `backlog/tasks` y `backlog/bugs`. Cambia `status:` en una
> tarjeta y se mueve de columna. Requiere el plugin **Dataview**.
>
> Para el orden de ejecución del agente, mira [[ready-queue]] (calcula qué está desbloqueado).

## 🔵 Backlog
```dataview
TABLE priority, epic, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE status = "backlog"
SORT priority ASC, id ASC
```

## 🟡 To Do
```dataview
TABLE priority, epic, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
WHERE status = "todo"
SORT priority ASC, id ASC
```

## 🟠 Doing
```dataview
TABLE priority, epic, estimate
FROM "backlog/tasks" OR "backlog/bugs"
WHERE status = "doing"
SORT priority ASC, id ASC
```

## ⛔ Blocked
```dataview
TABLE depends_on, priority, epic
FROM "backlog/tasks" OR "backlog/bugs"
WHERE status = "blocked"
SORT id ASC
```

## ✅ Done
```dataview
TABLE epic
FROM "backlog/tasks" OR "backlog/bugs"
WHERE status = "done"
SORT id ASC
```
