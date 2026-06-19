# 🔧 n8n Workflows — WinoWin Recepcionista

Workflows de n8n para automatizar la confirmación de citas y los recordatorios 24h del chatbot recepcionista de WinoWin.

---

## 📁 Workflows incluidos

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `confirmacion-cita.json` | Webhook | Recibe datos de cita confirmada → envía WhatsApp de confirmación |
| `recordatorio-24h.json` | Schedule | Cada hora consulta citas pendientes → envía recordatorio → marca como recordada |

---

## 🔄 Flujo detallado

### Workflow 1: WinoWin - Confirmación de Cita

```
[Webhook: POST /confirmacion-cita]
    ↓  Recibe {phone, name, service, date, time}
[Set: Construir mensaje]
    ↓  Añade campo "message" con texto personalizado
[HTTP Request: WhatsApp Cloud API]
    ↓  POST https://graph.facebook.com/v22.0/{phone_number_id}/messages
[Respond to Webhook]
    →  Responde {success: true} al chatbot
```

**Cuándo se dispara:** El chatbot (FastAPI) hace un POST al webhook de n8n cuando se confirma una cita, pasando los datos del cliente en el body JSON.

### Workflow 2: WinoWin - Recordatorio 24h

```
[Schedule Trigger: Cada hora]
    ↓
[HTTP Request: GET /api/appointments/pending-reminders]
    ↓  Llama al chatbot para obtener citas de mañana sin recordatorio
[IF: ¿count > 0?]
    ↓ true
[SplitInBatches: 1 por 1]
    ↓  Procesa cada cita individualmente
[Set: Construir mensaje]
    ↓  Añade campo "message" con texto de recordatorio
[HTTP Request: WhatsApp Cloud API]
    ↓  Envía recordatorio al cliente por WhatsApp
[HTTP Request: POST /api/appointments/{id}/mark-reminded]
    →  Marca la cita como recordada en el chatbot
```

**Cuándo se dispara:** Automáticamente cada hora. Consulta las citas de mañana que aún no tienen recordatorio.

---

## 📥 Cómo importar en n8n

### 1. Importar los workflows

1. Abre tu instancia de **n8n** (local o cloud)
2. Ve a **Workflows → Import from File**
3. Selecciona `confirmacion-cita.json` o `recordatorio-24h.json`
4. Repite para el otro workflow

### 2. Configurar variables de entorno en n8n

Ve a **Settings → Environment Variables** y añade:

```
WHATSAPP_TOKEN=EAAjTjCS5GSQBR...     # Token permanente de Meta Cloud API
WHATSAPP_PHONE_NUMBER_ID=1103593682842997  # ID del número de WhatsApp Business
CHATBOT_URL=http://localhost:8000    # URL base del chatbot (o URL de ngrok/túnel)
```

> ⚠️ **Importante:** Si el chatbot está expuesto vía ngrok, usa la URL de ngrok (ej: `https://xxxx-xx-xx-xx-xx.ngrok-free.app`).

### 3. Activar los workflows

Una vez importados y configuradas las variables:
- El workflow de **Confirmación** se activa al recibir un POST en su webhook
- El workflow de **Recordatorio** se ejecuta automáticamente cada hora (cambia el toggle a **Active**)

---

## 🔗 Endpoints del chatbot (necesarios)

El chatbot FastAPI expone dos endpoints nuevos para el workflow de recordatorio:

### `GET /api/appointments/pending-reminders`

Devuelve las citas de mañana que aún no tienen recordatorio enviado.

**Response:**
```json
{
  "appointments": [
    {
      "id": 1,
      "phone": "34123456789",
      "name": "María García",
      "service": "Corte de pelo mujer",
      "date": "2026-06-20",
      "time": "10:00"
    }
  ],
  "count": 1
}
```

### `POST /api/appointments/{id}/mark-reminded`

Marca una cita como recordada (establece `reminded_at` y crea registro en tabla `notifications`).

**Response:**
```json
{
  "success": true,
  "appointment_id": 1
}
```

---

## 🔌 Integración chatbot → n8n (Workflow de Confirmación)

Para que el chatbot llame al webhook de n8n cuando se confirma una cita, añade esta llamada en el código del chatbot (en `app/webhook_handler.py` o donde se maneje la confirmación):

```python
import httpx

async def notify_n8n_confirmation(phone: str, name: str, service: str, date: str, time: str):
    """Notify n8n workflow about a confirmed appointment."""
    n8n_webhook_url = "http://localhost:5678/webhook/confirmacion-cita"
    # O la URL de producción: "https://n8n.tudominio.com/webhook/confirmacion-cita"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(n8n_webhook_url, json={
                "phone": phone,
                "name": name,
                "service": service,
                "date": date,
                "time": time,
            })
    except Exception as e:
        logger.warning(f"⚠️ Failed to notify n8n: {e}")
```

---

## 🗄️ Base de datos — Nueva columna

Se añadió `reminded_at TEXT` a la tabla `appointments` (migración automática al iniciar el chatbot):

```sql
ALTER TABLE appointments ADD COLUMN reminded_at TEXT;
```

Esta columna se usa para saber qué citas ya recibieron recordatorio y evitar duplicados.

---

## 🧪 Probar los endpoints

```bash
# 1. Verificar que el chatbot está corriendo
curl http://localhost:8000/health

# 2. Crear una cita de prueba para mañana
curl -X POST "http://localhost:8000/api/appointments/book?service_id=1&client_name=Test&client_phone=34123456789&date_str=$(date -d '+1 day' +%Y-%m-%d)&start_time=10:00"

# 3. Consultar citas pendientes de recordatorio
curl http://localhost:8000/api/appointments/pending-reminders

# 4. Marcar una cita como recordada (usa el ID que devuelva el endpoint anterior)
curl -X POST http://localhost:8000/api/appointments/1/mark-reminded

# 5. Verificar que ya no aparece en pendientes
curl http://localhost:8000/api/appointments/pending-reminders
```

---

## 📊 Comparación: n8n vs APScheduler

| Característica | APScheduler (actual) | n8n (nuevo) |
|---------------|---------------------|-------------|
| Recordatorios | ✅ En Python, integrado | ✅ En n8n, desacoplado |
| Confirmación de cita | ❌ No implementado | ✅ Webhook + WhatsApp |
| Configuración | Cero (automático) | Requiere importar JSONs |
| Monitorización | Logs de Python | UI visual de n8n |
| Dependencia externa | No | n8n corriendo en el host |

Ambos sistemas pueden coexistir. El APScheduler en `app/scheduler.py` sigue funcionando para recordatorios y seguimientos, mientras que n8n añade la confirmación inmediata de citas y una alternativa visual para los recordatorios.

---

## ⚠️ Notas importantes

1. **n8n debe estar corriendo** en el host (puerto 5678 por defecto) para que los webhooks funcionen
2. **Variables de entorno**: Asegúrate de que `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` y `CHATBOT_URL` estén configurados en n8n
3. **URL del chatbot**: Si usas ngrok, actualiza `CHATBOT_URL` cada vez que cambie la URL del túnel
4. **Meta Cloud API**: El token de WhatsApp debe ser permanente y tener permisos para enviar mensajes

---

*WinoWin Recepcionista · n8n Workflows · Junio 2026*
