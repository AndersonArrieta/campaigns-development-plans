---
title: "Roadmap por epic"
type: dashboard
---

# 🗺️ Roadmap (por capacidad, no por tiempo)

## Progreso por epic
```dataview
TABLE
  length(rows) AS "Total",
  length(filter(rows.status, (s) => s = "done")) AS "Done",
  length(filter(rows.status, (s) => s != "done")) AS "Pendientes"
FROM "backlog/tasks" OR "backlog/bugs"
GROUP BY epic
SORT epic ASC
```

## Todo el backlog agrupado por epic
```dataview
TABLE status, priority, estimate, depends_on
FROM "backlog/tasks" OR "backlog/bugs"
SORT epic ASC, id ASC
GROUP BY epic
```
