# N8N Workflows — WinoWin Recepcionista

> ⚠️ **Documentación complementaria.**  
> El motor real de recordatorios y seguimiento es **Python/APScheduler** en `app/scheduler.py`.  
> Estos workflows n8n se proporcionan como referencia y alternativa para clientes que prefieran usar n8n como orquestador.

---

## 📁 Workflows incluidos

| Archivo | Descripción |
|---------|-------------|
| `recordatorio_cita.json` | Escanea cada 30 min citas que empiezan mañana → envía recordatorio WhatsApp 24h antes |
| `seguimiento_post_servicio.json` | Escanea cada 30 min citas finalizadas hace 2h → envía seguimiento pidiendo reseña |

---

## 🔧 Cómo importar en n8n

1. Abre tu instancia de **n8n** (local o cloud).
2. Ve a **Workflows → Import from File**.
3. Selecciona el archivo `.json` del workflow.
4. Configura las **credenciales**:

### Credencial necesaria: PostgreSQL

Ambos workflows usan el nodo **Postgres** para consultar la base de datos SQLite.  
En n8n, necesitas:

- **Host**: `localhost` (o IP del servidor de la BD)
- **Database**: `chatbot.db` (ruta completa en el servidor)
- **User**: (vacío para SQLite en modo lectura)
- **Password**: (vacío)

> Alternativa: sustituye el nodo Postgres por un **Webhook Node** que llame a la API del backend (`GET /api/appointments?date_str=YYYY-MM-DD`). Los JSON actuales usan Postgres para simplicidad documental.

### Variables de entorno en n8n

Los workflows usan variables `{{$env.VAR}}` que debes configurar en n8n:

```
PHONE_NUMBER_ID=1103593682842997
WHATSAPP_TOKEN=EAA...
```

Ve a **Settings → Environment Variables** en n8n para añadirlas.

---

## 🔄 Flujo de cada workflow

### `recordatorio_cita.json`

```
[Schedule Trigger (cada 30 min)]
    → [Postgres: SELECT appointments para mañana sin recordatorio]
    → [Code: Construir mensaje "¡Hola X! Mañana a las HH:MM tienes tu servicio..."]
    → [HTTP Request: POST a Meta Cloud API /messages]
    → [Postgres: INSERT INTO notifications (type='reminder', status='sent')]
```

### `seguimiento_post_servicio.json`

```
[Schedule Trigger (cada 30 min)]
    → [Postgres: SELECT appointments finalizadas hace 2h sin followup]
    → [Code: Construir mensaje "¿Nos dejas una reseña? ⭐"]
    → [HTTP Request: POST a Meta Cloud API /messages]
    → [Postgres: INSERT INTO notifications (type='followup', status='sent')]
```

---

## ⚡ Motor real: Python/APScheduler

El sistema productivo usa `app/scheduler.py` con **APScheduler** (AsyncIOScheduler):

- Se inicia en el evento `startup` de FastAPI (`app/main.py`)
- Escanea cada 30 minutos con `get_pending_notifications()`
- Las notificaciones se crean automáticamente al **reservar una cita** (`book_appointment()` en `database.py`)
- Envía mensajes vía `whatsapp_client.send_message()` (Meta Cloud API)

**Ventajas del motor Python vs n8n:**
- Sin dependencia externa — todo corre en el mismo proceso FastAPI
- Las notificaciones se programan al crear la cita (no solo por polling)
- Logs unificados con el resto del sistema
- Cero configuración adicional para el cliente

---

## 📊 Tabla `notifications` (SQLite)

```sql
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER NOT NULL,
    type TEXT NOT NULL,        -- 'reminder' | 'followup'
    scheduled_for TEXT NOT NULL, -- ISO timestamp
    sent_at TEXT,
    status TEXT DEFAULT 'pending', -- pending | sent | failed
    wa_message_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
```

---

## ✅ Verificación

Para comprobar que el sistema funciona:

```bash
# 1. Crear una cita de prueba
curl -X POST "http://localhost:8000/api/appointments/book?service_id=1&client_name=Test&client_phone=34123456789&date_str=$(date -d '+1 day' +%Y-%m-%d)&start_time=10:00"

# 2. Ver notificaciones programadas
sqlite3 data/chatbot.db "SELECT * FROM notifications;"

# 3. Ejecutar el scan manualmente (desde Python)
python -c "
import asyncio
from app.scheduler import scan_and_send_notifications
asyncio.run(scan_and_send_notifications())
"

# 4. Verificar logs
tail -f nohup.out  # o journalctl según despliegue
```
