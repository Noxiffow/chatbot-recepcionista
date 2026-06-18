# 🤖 WinoWin Recepcionista — Chatbot WhatsApp Business con IA

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Groq](https://img.shields.io/badge/IA-Groq%20Llama%203-orange)](https://groq.com)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-Cloud%20API-brightgreen?logo=whatsapp)](https://developers.facebook.com/docs/whatsapp)

Chatbot recepcionista virtual para WhatsApp Business con inteligencia artificial. Responde automáticamente a clientes, consulta un catálogo de servicios real con precios, gestiona citas con disponibilidad en tiempo real, mantiene conversaciones multi-turno con contexto, y deriva a un humano cuando es necesario.

---

## ✨ Qué hace

- 📩 **Recibe mensajes** de WhatsApp através de la API oficial de Meta (Cloud API).
- 🧠 **Procesa con IA** cada mensaje usando Groq (llama-3.3-70b) con un prompt personalizado por tipo de negocio.
- 💇 **Consulta el catálogo** de servicios y precios en tiempo real (SQLite).
- 📅 **Gestiona citas** con disponibilidad real: comprueba huecos libres, reserva, cancela.
- 💬 **Conversaciones multi-turno** con memoria de contexto y máquina de estados.
- 👥 **Deriva a humano** cuando detecta quejas, frustración o petición explícita.
- 📊 **Dashboard web** para ver mensajes, estadísticas y citas.

---

## 🏗️ Stack tecnológico

| Capa | Tecnología |
|---|---|
| **API WhatsApp** | Meta Cloud API (Graph API v22.0) — oficial, sin riesgo de ban |
| **Backend** | FastAPI (Python 3.11+) — async, webhooks, REST |
| **IA** | Groq API — llama-3.3-70b-versatile |
| **Base de datos** | SQLite (aiosqlite) — mensajes, conversaciones, servicios, citas |
| **Servidor** | Uvicorn — ASGI, producción |
| **Túnel desarrollo** | ngrok |

---

## 📁 Estructura del proyecto

```
chatbot-recepcionista/
├── app/
│   ├── main.py              ← FastAPI: webhook + endpoints REST + dashboard
│   ├── config.py             ← Configuración centralizada (.env loader)
│   ├── database.py           ← SQLite: mensajes, servicios, citas, agenda
│   ├── webhook_handler.py    ← Parser + pipeline de procesamiento completo
│   ├── groq_client.py        ← Cliente IA asíncrono (Groq)
│   ├── prompts.py            ← Prompt del sistema (personalizable por negocio)
│   ├── whatsapp_client.py    ← Cliente WhatsApp Cloud API (send, health)
│   ├── conversation_state.py ← Máquina de estados (Fase 7)
│   └── context_manager.py    ← Gestión de contexto multi-turno (Fase 7)
├── data/
│   └── chatbot.db            ← Base de datos SQLite
├── docs/
│   ├── README_CLIENTE.md     ← Manual para el cliente final (NO técnico)
│   ├── SETUP_TECNICO.md      ← Guía de instalación y despliegue
│   └── CONFIG_NEGOCIO.md     ← Cómo personalizar el negocio sin tocar código
├── .env.example              ← Plantilla de variables de entorno
├── requirements.txt
└── README.md                 ← Este archivo
```

---

## ⚡ Arranque rápido (desarrollo)

```bash
# 1. Clonar
git clone <repo> && cd chatbot-recepcionista

# 2. Entorno virtual
python3 -m venv venv && source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar .env
cp .env.example .env
# Edita .env con tus tokens (WHATSAPP_TOKEN, GROQ_API_KEY, etc.)

# 5. Arrancar
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 6. Exponer a Internet (para el webhook de Meta)
ngrok http 8000
```

El servidor estará en `http://localhost:8000`:

| Endpoint | Descripción |
|---|---|
| `/` | Health check |
| `/health` | Estado detallado |
| `/webhook` | Webhook de Meta (GET verify + POST receive) |
| `/dashboard` | Panel web con mensajes y estadísticas |
| `/api/messages` | Últimos mensajes (JSON) |
| `/api/stats` | Estadísticas (JSON) |
| `/api/services` | Catálogo de servicios |
| `/api/availability?date_str=2026-06-18` | Disponibilidad para una fecha |
| `/api/availability/dates` | Próximas fechas con huecos libres |
| `/api/appointments?date_str=2026-06-18` | Citas agendadas |
| `/api/test-chat?msg=Hola` | Probar el chat sin webhook |

---

## 📚 Documentación

- **[Manual del Cliente](docs/README_CLIENTE.md)** — Guía NO técnica para el negocio que usa el chatbot.
- **[Guía de Despliegue](docs/SETUP_TECNICO.md)** — Instalación, configuración y puesta en producción.
- **[Configuración del Negocio](docs/CONFIG_NEGOCIO.md)** — Cómo cambiar servicios, horarios, tono y personalidad sin programar.

---

## 🔧 Variables de entorno

```env
WHATSAPP_TOKEN=...      # Token permanente de Meta Cloud API
PHONE_NUMBER_ID=...     # ID del número de WhatsApp
WABA_ID=...             # ID de cuenta WhatsApp Business
GROQ_API_KEY=gsk_...    # API key de Groq (gratis)
BUSINESS_NAME=...       # Nombre del negocio (opcional)
BUSINESS_TYPE=...       # Tipo de negocio (opcional)
```

Ver [`.env.example`](.env.example) para la plantilla completa.

---

## ⚠️ Aviso importante

> **La cuenta de Meta configurada actualmente es de DESARROLLO PERSONAL** (cuenta de Jotadev).
>
> Para usar este chatbot en producción, el cliente debe:
> 1. Crear su **propia cuenta de Meta Business verificada**.
> 2. Generar su **propio token de acceso permanente**.
> 3. Configurar un **método de pago** (aunque los mensajes de atención al cliente son gratis).
> 4. Verificar la **empresa** ante Meta.
>
> Consulta la [Guía de Despliegue](docs/SETUP_TECNICO.md) para los pasos detallados.

---

## 📊 Costes de producción

| Concepto | Coste |
|---|---|
| Alojamiento (VPS) | ~5-10€/mes |
| Mensajes de WhatsApp (atención al cliente) | **0€** (gratis) |
| Mensajes de WhatsApp (marketing) | ~0.05-0.09€/msg |
| IA (Groq) | Capa gratuita suficiente para MVP |
| **Total mensual estimado** | **~5-10€** |

---

## 📦 Dependencias

- `fastapi` ≥ 0.115 — Framework web
- `uvicorn[standard]` ≥ 0.30 — Servidor ASGI
- `httpx` ≥ 0.27 — HTTP client async
- `pydantic` ≥ 2.0 — Validación de datos
- `groq` ≥ 1.0 — Cliente IA
- `aiosqlite` ≥ 0.20 — SQLite async

---

## 🗺️ Fases del proyecto

| Fase | Estado |
|---|---|
| 1. Registro Meta + App | ✅ Completada |
| 2. Backend FastAPI + Webhook | ✅ Completada |
| 3. Integración IA (Groq) | ✅ Completada |
| 4. Catálogo de productos (SQLite) | ✅ Completada |
| 5. Consultas al catálogo + Disponibilidad | ✅ Completada |
| 5B. Sistema de reservas | ✅ Completada |
| 6. Integración n8n | 🔜 Pospuesta (mejora futura) |
| 7. Sesiones + Contexto + Handoff | ✅ Completada |
| 8. Documentación y cierre | ✅ Completada |

---

*WinoWin Recepcionista · v1.0 · Junio 2026*
