# Scripts de apoyo — `pruebas-queuer`

## `leer_segmento_kafka.py`

Muestra el segmento y el destino Kafka (tópico de campañas, tópico de notificaciones y nombre del secreto) que `queuer_ms` usa para un `applicationIdentifier` en `dev`. Lee la configuración de segmentos de DynamoDB con el mismo algoritmo que `SegmentRoutingAdapter` ([publicación en Kafka §1](../docs/publicacion-kafka.md#1-enrutamiento-por-segmento-segmentroutingadapter)).

- **Solo lectura:** hace un único `GetItem` sobre `nu0284001-artemis-chatbots-platform-dev-config-data`.
- **No vuelca la configuración completa:** solo imprime el segmento y las tres claves `kafka`. `secret_campaigns` es el **nombre** del secreto, no su contenido.

### Requisitos
- Python 3.8 o superior (`py --version`).
- `boto3`: `py -m pip install boto3`.
- Credenciales temporales de AWS de la cuenta de `dev` con permiso `dynamodb:GetItem` sobre la tabla.
- VPN conectada, si tu red lo exige para llegar a AWS.

### Credenciales
El script **no** acepta credenciales como argumentos, así no quedan en el historial de PowerShell. Tienes dos opciones:

1. **Que el script las pida (recomendado):** ejecútalo sin definir nada. Si no encuentra credenciales en el entorno, pide `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y `AWS_SESSION_TOKEN`. Al pegarlas no se muestran en pantalla.
2. **Variables de entorno de la sesión de PowerShell:** se pierden al cerrar la ventana.
   ```powershell
   $env:AWS_ACCESS_KEY_ID = "..."
   $env:AWS_SECRET_ACCESS_KEY = "..."
   $env:AWS_SESSION_TOKEN = "..."
   ```

No pegues credenciales en archivos, commits ni chats. La salida del script no las incluye y se puede compartir.

### Ejecución (PowerShell)
Desde la carpeta `pruebas-queuer`:

```powershell
py scripts\leer_segmento_kafka.py --app-id others-test
```

Para comparar con los valores que usa la suite de aceptación:

```powershell
py scripts\leer_segmento_kafka.py --app-id others-test --comparar `
  --kafka-batch-topic customerforeignsubsidiarycampaignexecution.initiatecampaignv1 `
  --kafka-online-topic customerforeignsubsidiarycampaignmanagement.executenotificationv1 `
  --kafka-secret-name nu0284001-artemis-dev-secret-operative-eda-composicion-nmt
```

Ejemplo de salida (valores ilustrativos):

```
Credenciales: tomadas del entorno (variables AWS_*, perfil o sesion).

applicationIdentifier : others-test
Segmento              : others
kafka.campaigns        : <topico de campanas>
kafka.notifications    : <topico de notificaciones>
kafka.secret_campaigns : <nombre del secreto>

Comparacion con la suite de aceptacion:
  kafkaBatchTopic   DISTINTO  usado=customerforeign...  queuer=<topico de campanas>
  kafkaOnlineTopic  OK        usado=...  queuer=...
  kafkaSecretName   OK        usado=...  queuer=...
```

Código de salida: `0` si el destino está completo (y, con `--comparar`, todo coincide); `2` si falta algún valor o hay diferencias; `1` ante errores de credenciales, permisos o conexión.

### Otras opciones
- `--table`, `--component`, `--config-name`, `--region`: para otra tabla o ambiente (por defecto, los de `dev`).
- `--desde-archivo RUTA`: lee un JSON local en vez de AWS. Acepta la configuración directa o la salida de `aws dynamodb get-item`. Sirve para probar sin credenciales.
- `--help`: ayuda completa (no requiere credenciales ni `boto3`).

## `e2e_rendimiento_queuer.py`

Prueba E2E de rendimiento por el queuer con llamadas HTTP directas, sin JMeter ([T-039](../backlog/tasks/T-039-script-local-e2e-rendimiento-queuer.md)). Hace lo mismo que los grupos `GH_campaignsQueuer` / `GH_notificationsQueuer` de `SC_whatsappJMeterTest.jmx`:

1. Pide un token `client_credentials` a Cognito (igual que `Tx_oauthToken`).
2. Envía `POST /campaigns` y `POST /notifications` al queuer con los bodies de `ReqCampaignsQueuer` / `ReqNotificationsQueuer`: `metadata.Id` = `qe2e-<runId>-<uuid>` y `userIdentifier` ficticio (`57` + 10 dígitos). Exige `202` y `status = accepted`.
3. Verifica la entrega en `GET <fakechannel>/whatsapp/get-messages/<userIdentifier>`: el primer mensaje debe tener `to` = usuario, `type` = `text` y `text.body` = mensaje esperado (igual que `ReqInteraction2*`).
4. Imprime un resumen por flujo: peticiones, `202`, entregas, fallos por motivo, p50/p95/p99 del `POST` y de la transacción completa, y TPS efectivos.

- **Cada `202` es un mensaje real** en el ambiente: pide confirmación antes de enviar (`--si` para no preguntar) y no supera 1 TPS ni 60 s salvo `--forzar` (hasta tener los límites acordados en [T-033](../backlog/tasks/T-033-prerrequisitos-e2e-rendimiento-qa.md)).
- Solo usa la librería estándar de Python (3.8 o superior). No imprime ni guarda el token ni el `client_secret`.
- Solo WhatsApp. Teams queda fuera de alcance mientras su pool de usuarios no reciba entregas ([T-035](../backlog/tasks/T-035-e2e-rendimiento-queuer-teams.md)).

### Variables
Las carga `qe2e_config.py` (compartido con el script de JMeter de T-040). Cada variable se toma, en este orden, de:

1. La opción de la línea de comandos (`--host`, `--prefix`, `--cognito-url`, `--client-id`, `--fakechannel-url`).
2. La variable de entorno `QE2E_<NOMBRE>` (p. ej. `QE2E_HOST`). Lleva prefijo para no chocar con variables del sistema como `HOST`.
3. El archivo `--env-file` (formato `KEY=VALUE`, mismos nombres que `queuer-qa.env`). Si no se indica, usa `queuer-qa.env` cuando existe.
4. La consola: pide lo que falte. `CLIENT_SECRET` no se acepta como opción y se pide sin mostrarlo.

| Variable | Qué es | QA |
|---|---|---|
| `HOST` | URL base del queuer | `https://informacion-ext-qa.apps.ambientesbc.com` |
| `PREFIX` | Prefijo de las rutas del queuer | `/artemis/platform/queuer/v1` |
| `COGNITO_URL` | Endpoint del token | `https://chatbots-artemis-qa.auth.us-east-1.amazoncognito.com/oauth2/token` |
| `CLIENT_ID` / `CLIENT_SECRET` | Cliente `client_credentials` autorizado por la `AuthorizationPolicy` del queuer | los de `queuer-qa.env` |
| `ENDPOINT_GET_MESSAGE_FAKE` | Base del fakechannel, sin `/whatsapp/get-messages` | `https://informacion-ext-qa.apps.ambientesbc.com/artemis/platform/fake-channel/v1` |

Para **dev**, copia la plantilla y complétala (los `*.env` están ignorados por git):

```bash
cp scripts/e2e-rendimiento.env.example queuer-dev.env
```

En dev revisa también los datos de la prueba: un `--app-id` con segmento Kafka completo que `platform_campaigns_ms` entregue en el fakechannel (las suites de dev usan `others-test`, [T-003](../backlog/tasks/T-003-datos-prueba-kafka-dev.md)), y `--nodo` / `--mensaje-esperado` si el nodo `N-03-99-10` no existe allí.

### Ejecución (bash en WSL)
Desde la carpeta `pruebas-queuer`:

```bash
# Ver la configuración y un body por flujo, sin pedir token ni enviar
python3 scripts/e2e_rendimiento_queuer.py --env-file queuer-qa.env --dry-run

# Corrida corta en QA: 1 TPS, 10 s, campañas y notificaciones (20 mensajes reales)
python3 scripts/e2e_rendimiento_queuer.py --env-file queuer-qa.env --flujo ambos --tps 1 --duracion 10 --salida qe2e-qa.csv

# Dev, solo notificaciones, con otro appId y sin validar el certificado (host int-*)
python3 scripts/e2e_rendimiento_queuer.py --env-file queuer-dev.env --flujo notifications \
  --app-id others-test --insecure --duracion 5
```

Ejemplo de resumen:

```
Resumen
  campaigns
    peticiones          : 10
    202 accepted        : 10
    entregas verificadas: 10
    POST p50/p95/p99    : 420 ms / 521 ms / 530 ms
    Tx   p50/p95/p99    : 1100 ms / 1260 ms / 1300 ms
    TPS efectivos       : 1.00
```

### Otras opciones
- `--flujo campaigns|notifications|ambos`, `--tps`, `--duracion`: carga de cada flujo. Con `ambos`, cada flujo va a `--tps`.
- `--hilos`: peticiones en curso a la vez (envío + verificación). Si la verificación tarda, súbelo para mantener el ritmo.
- `--app-id`, `--canal`, `--nodo`, `--mensaje-esperado`, `--retries`: datos del body (por defecto, los de `DT_Campaigns.txt`).
- `--intentos` / `--intervalo`: consultas a `get-messages` por petición (por defecto 20 cada 1 s).
- `--timeout`, `--insecure`: timeout HTTP y omitir la validación TLS.
- `--salida RUTA.csv`: una fila por petición (`metadata.Id`, usuario, código, tiempos, entregada, motivo).
- `--verbose`: detalle por petición.

Código de salida: `0` todo `202` y entregado; `2` hubo rechazos o entregas no verificadas; `1` error de configuración, de token o de conexión.
