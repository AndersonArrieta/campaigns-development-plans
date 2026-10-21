---
title: "Bugs"
type: dashboard
---

# 🐞 Bugs

> Se genera solo desde el frontmatter de `backlog/bugs/`. Requiere el plugin **Dataview**.
>
> Un bug `P0` sin `depends_on` sube al tope de [[ready-queue]] automáticamente.

## 🔴 Abiertos
```dataview
TABLE priority, status, epic, affects
FROM "backlog/bugs"
WHERE status != "done"
SORT priority ASC, id ASC
```

## ✅ Cerrados
```dataview
TABLE epic, affects
FROM "backlog/bugs"
WHERE status = "done"
SORT id ASC
```
