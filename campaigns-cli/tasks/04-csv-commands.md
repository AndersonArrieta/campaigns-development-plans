# T-04 — Comandos `csv`

- **Grupo:** `csv`
- **Secciones del plan:** §2.1, §6
- **Depende de:** T-01

## Objetivo

Generar archivos CSV de campaña válidos para el ingester y validar archivos existentes, sin necesidad de AWS.

## Formato de referencia

Tomado de `csv-test.csv`:

```
app_id;canal;usuario;fecha_inicio;fecha_fin;dias;horas;nodo;parametros
others-test;WhatsApp;573232540390;13/10/2026;13/10/2026;martes;10;N-03-99-10;
```

| Columna | Regla de validación (propuesta) |
|---|---|
| `app_id` | Obligatorio, no vacío. |
| `canal` | Obligatorio. Valores conocidos: `WhatsApp`, `Teams` (confirmar lista completa con el ingester). |
| `usuario` | Obligatorio. Para `WhatsApp`: solo dígitos, con indicativo de país. |
| `fecha_inicio`, `fecha_fin` | `dd/mm/yyyy`; `fecha_inicio <= fecha_fin`. |
| `dias` | Días de la semana en español, en minúscula (`lunes`…`domingo`). Confirmar separador si hay varios. |
| `horas` | Entero 0–23. Confirmar separador si hay varias. |
| `nodo` | Obligatorio; patrón `N-\d{2}-\d{2}-\d{2}` (confirmar). |
| `parametros` | Opcional. Confirmar formato esperado por el ingester. |

> Las reglas marcadas "confirmar" se deben contrastar con la validación real de `ingester_Lambda` antes de cerrar la task. Si el ingester ya tiene un validador, replicar sus reglas y citar el archivo de origen en un comentario.

## Archivos

| Archivo | Cambio |
|---|---|
| `src/campaigns_cli/services/csv_service.py` | `CampaignRow` (dataclass), `generate_rows(...)`, `write_csv(rows, path)`, `validate_csv(path) -> list[ValidationIssue]`. |
| `src/campaigns_cli/commands/csv_cmd.py` | Subgrupo `csv` con `generate` y `validate`. |
| `tests/test_csv_service.py` | Pruebas del servicio. |
| `tests/fixtures/csv-test.csv` | Copia del CSV de referencia. |

## Pasos

1. `csv generate`:
   ```text
   campaigns csv generate --users 573232540390,573001112233 --canal WhatsApp \
       --fecha 13/10/2026 [--fecha-fin 13/10/2026] --hora 10 --nodo N-03-99-10 \
       [--app-id others-test] [--parametros "k=v"] [-o campaign.csv]
   ```
   - `--app-id` toma por defecto `CLI_TEST_APP_ID`, para que luego `dynamo purge` pueda limpiar.
   - `--fecha` acepta `hoy` y `mañana`; `dias` se calcula a partir de la fecha si no se pasa `--dias`.
   - `--hora` acepta `+N` (hora actual + N) para pruebas rápidas.
   - Sin `-o`, escribe en `campaign-<timestamp>.csv`.
   - Separador `;`, codificación UTF-8 sin BOM (confirmar si el ingester espera BOM), salto de línea `\n`.
2. `csv validate <archivo>`:
   - Verifica encabezado exacto y orden de columnas, separador `;`, número de columnas por fila y las reglas de la tabla.
   - Reporta los problemas por fila y columna; exit code 1 si hay errores.
3. Usar `csv` de la librería estándar (sin pandas).

## Pruebas

- `validate` sobre `tests/fixtures/csv-test.csv` → sin problemas.
- `generate` → `validate` del archivo generado → sin problemas (ida y vuelta).
- Casos inválidos: separador `,`, fecha `2026-10-13`, `fecha_inicio > fecha_fin`, hora `24`, día `tuesday`, columna faltante → un problema por cada caso con fila y columna.
- `--fecha hoy` sin `--dias` → `dias` coincide con el día de la semana de hoy.

## Criterios de terminado

- [ ] Un CSV generado por la CLI es aceptado por el ingester en dev (se verifica en la T-09).
- [ ] Reglas "confirmar" revisadas contra el código del ingester.
- [ ] Pruebas, ruff y mypy en verde.
- [ ] Commit (lo hace el desarrollador).
