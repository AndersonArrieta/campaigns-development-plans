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
