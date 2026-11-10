---
id: B-005
aliases: [B-005]
title: "Los .jmx E2E no abren en la GUI de JMeter: __intSum del Throughput Shaping Timer del queuer recibe una variable sin resolver"
status: done
priority: P1
epic: E-e2e-rendimiento
estimate: S
depends_on: []
type: bug
affects: [T-034, T-035]
created: 2026-11-10
---

# B-005 — Los `.jmx` E2E no abren en la GUI de JMeter: `__intSum` del Throughput Shaping Timer del queuer recibe una variable sin resolver

## Reproducción
- **Pasos:**
  1. JMeter 5.5 con los plugins `casutg` 2.10, `tst` 2.6 y `cmn-jmeter` 0.7 en `lib/ext`.
  2. Abrir en la GUI `Back/E2E/teams/SC_teamsJMeterTest.jmx` (rama `feature/8016357-queuer-e2e-performance-test` del repo PE).
- **Esperado:** el script abre y se puede editar.
- **Observado:** `For input string: "${V_campaignsQueuerDuration}"` y el script no abre. Le pasa al usuario (WSL) y a un compañero desde su equipo. `SC_whatsappJMeterTest.jmx` tiene los mismos timers y se espera el mismo error.

## Causa (si se conoce)
- La tercera columna del `load_profile` de los timers `jp@gc - Throughput Shaping Timer campaignsQueuer` / `notificationsQueuer` (T-034 y T-035) es `${__intSum(${__P(rampUp*Queuer,0)},${V_*QueuerDuration},300)}`.
  - Teams: líneas ~7926 y ~8194.
  - WhatsApp: líneas ~8314 y ~8592.
- Al cargar el script, la GUI del timer evalúa las celdas para dibujar el perfil. En ese momento las variables de `User Defined Variables` (`V_*`) no existen, así que `__intSum` recibe el texto literal `${V_campaignsQueuerDuration}` y lanza `NumberFormatException`.
  - En `jmeter -n` no pasa: el timer se evalúa con las variables ya definidas. Por eso no se detectó en las verificaciones de T-034 y T-035, que fueron todas sin GUI.
- Los timers existentes (desactivados) usan `${__P(durationText,0)}` directo, y `__P` sí se resuelve sin variables.
- Fix propuesto: dentro de los timers del queuer, usar las propiedades en vez de las variables `V_*`, con los mismos valores por defecto que hoy:
  - `${__intSum(${__P(rampUpCampaignsQueuer,0)},${__P(campaignsQueuerDuration,0)},300)}`
  - columnas de TPS: `${__P(campaignsQueuerTps,0)}`
  - lo mismo para notificaciones, en los dos `.jmx`.

  El valor en ejecución no cambia, porque `V_*QueuerDuration` / `V_*QueuerTps` ya son `${__P(...,0)}`.

## Criterios de aceptación
- [x] `SC_teamsJMeterTest.jmx` y `SC_whatsappJMeterTest.jmx` abren en la GUI de JMeter 5.5 (con los plugins) sin error.
- [x] Ninguna celda de `load_profile` de los timers del queuer referencia variables `V_*`.
- [x] Con los usuarios del queuer en `0`, `jmeter -n` genera las mismas muestras que antes del fix.
- [x] Con los grupos del queuer activos, el perfil del timer es el mismo que antes (TPS y duración `rampUp + duration + 300 s`): se comprueba con un mock local o con una corrida corta aprobada por el usuario.

## Verificación
```bash
cd /mnt/c/Users/AndersonElitArrietaR/repos/NU0284001_Artemis_Chatbots_Platform_PE/Back/E2E
# Regresión sin GUI: falla hoy (4 líneas por archivo), pasa tras el fix (0 y 0)
grep -cE '__intSum\([^)]*\$\{V_|<stringProp name="[^"]*">\$\{V_[a-zA-Z]*QueuerTps\}' teams/SC_teamsJMeterTest.jmx whatsapp/SC_whatsappJMeterTest.jmx
# Regresión de carga: configura la GUI real del timer (VariableThroughputTimerGui.configure) con cada
# VariableThroughputTimer de los .jmx, como al abrirlos. Antes del fix: failures=4 (exit 1); después: failures=0 (exit 0).
/usr/lib/jvm/java-17-openjdk-amd64/bin/java -Djava.awt.headless=true -cp "/opt/jmeter/lib/*:/opt/jmeter/lib/ext/*" \
  groovy.ui.GroovyMain LoadTimersInGui.groovy "$PWD/teams/SC_teamsJMeterTest.jmx" "$PWD/whatsapp/SC_whatsappJMeterTest.jmx"
# Manual: abrir los dos .jmx en la GUI (jmeter -t <archivo>) sin error.
```

<details><summary><code>LoadTimersInGui.groovy</code></summary>

```groovy
import org.apache.jmeter.util.JMeterUtils
import org.apache.jmeter.save.SaveService
import org.apache.jorphan.collections.HashTree
import kg.apc.jmeter.timers.VariableThroughputTimer
import kg.apc.jmeter.timers.VariableThroughputTimerGui

def home = '/opt/jmeter'
JMeterUtils.setJMeterHome(home)
JMeterUtils.loadJMeterProperties("${home}/bin/jmeter.properties")
JMeterUtils.initLocale()
SaveService.loadProperties()

int failures = 0
args.each { path ->
    HashTree tree = SaveService.loadTree(new File(path))
    List<VariableThroughputTimer> timers = []
    def walk
    walk = { HashTree t -> t.list().each { k -> if (k instanceof VariableThroughputTimer) timers << k; walk(t.getTree(k)) } }
    walk(tree)
    timers.each { timer ->
        try {
            new VariableThroughputTimerGui().configure(timer)
            println "OK   ${new File(path).name} :: ${timer.name}"
        } catch (Throwable e) {
            failures++
            def c = e; while (c.cause) c = c.cause
            println "FAIL ${new File(path).name} :: ${timer.name} -> ${c.class.simpleName}: ${c.message}"
        }
    }
}
println "failures=${failures}"
System.exit(failures ? 1 : 0)
```
</details>

## Notas
- Reportado por el usuario el 2026-11-10: le pasa a él y a un compañero al abrir `SC_teamsJMeterTest.jmx` desde la GUI.
- Antes de este error estaba el de los plugins faltantes (`CannotResolveClassException: ConcurrencyThreadGroup`). Ese es del entorno, no de este bug: se resuelve con `casutg` 2.10, `tst` 2.6 y `cmn-jmeter` 0.7 en `lib/ext`.
- Los commits de T-034 (`9856905`) y T-035 (`c72cd39`) ya están publicados en la rama del repo PE: el fix va en un commit nuevo en la misma rama.
- 2026-11-10 — Corregido en la rama `feature/8016357-queuer-e2e-performance-test` del repo PE, sin commit: en `SC_teamsJMeterTest.jmx` y `SC_whatsappJMeterTest.jmx`, las celdas de los timers `campaignsQueuer` / `notificationsQueuer` usan `${__P(*QueuerTps,0)}` y `${__intSum(${__P(rampUp*Queuer,0)},${__P(*QueuerDuration,0)},300)}` en lugar de `V_*`. Son 6 líneas por archivo, con CRLF y XML válido. Las variables `V_*QueuerTps` / `V_*QueuerDuration` siguen definidas, aunque ya ningún elemento las usa.
- 2026-11-10 — Verificación local (JMeter 5.5 + JRE 17 + `casutg` 2.10 / `tst` 2.6 / `cmn-jmeter` 0.7):
  - Regresión de la GUI (`LoadTimersInGui.groovy`):
    - Antes del fix: `failures=4`, 2 por script. Error: `NumberFormatException: For input string: "${V_campaignsQueuerDuration}"` / `"${V_notificationsQueuerDuration}"`, el mismo que reportó el usuario.
    - Después: `failures=0` en los 34 timers de los dos scripts.
    - Los timers existentes con `${V_tps}` solo dejan un `ERROR` en el log y no impiden abrir el script.
  - `grep`: 4 líneas por archivo antes del fix, 0 después.
  - Perfil en ejecución: las celdas se evaluaron con las `User Defined Variables` resueltas, en `HEAD` y en la versión corregida, y dan lo mismo.
    - Por defecto: `[0, 0, 300]`.
    - Con `rampUp=10`, `duration=60`, `tps=1` (campañas) y `5`, `45`, `2` (notificaciones): `[1, 1, 370]` y `[2, 2, 350]`.
  - `jmeter -n` con los valores por defecto (usuarios del queuer en `0`): `HEAD` y la versión corregida generan las mismas muestras en Teams y en WhatsApp.
    - Configuración: copias temporales con el Backend Listener desactivado y el cliente Cognito de `queuer-qa.env` por `-q`. Sin credenciales AWS, para que `GH_setup` se detenga y no corra ningún grupo en QA.
    - Resultado: `Tx_oauthToken` OK y `Tx_secretManager` falla.
    - El secreto no aparece en `jmeter.log` ni en el `.jtl`, y no quedaron copias ni `.properties`.
- Sin marcar, no bloquea el cierre: abrir los dos `.jmx` a mano en la GUI (`jmeter -t`). La regresión usa la misma clase de GUI que fallaba, pero en modo headless. Falta también el commit en el repo PE, que requiere confirmación del usuario.
