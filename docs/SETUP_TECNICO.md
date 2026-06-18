# 🛠️ Guía de Despliegue Técnico — WinoWin Recepcionista

> **Para:** La persona que instala el chatbot en el servidor del cliente.  
> **Requisitos previos:** Conocimientos básicos de Linux, Python, y redes.

---

## 📋 Requisitos del sistema

| Requisito | Mínimo | Recomendado |
|---|---|---|
| **Sistema operativo** | Ubuntu 22.04+, Debian 12+ | Ubuntu 24.04 LTS |
| **Python** | 3.11+ | 3.13+ |
| **RAM** | 512 MB | 1 GB |
| **Disco** | 2 GB | 5 GB (para logs y BD) |
| **Red** | Conexión estable a Internet | IP fija o dominio |

---

## 📦 1. Preparar el servidor

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python + pip + venv
sudo apt install -y python3 python3-pip python3-venv

# Instalar git (para clonar el repo)
sudo apt install -y git
```

---

## 📂 2. Clonar e instalar el proyecto

```bash
# Clonar el repositorio
git clone <URL_DEL_REPO> /opt/chatbot-recepcionista
cd /opt/chatbot-recepcionista

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

---

## ⚙️ 3. Configurar el archivo .env

Copia el archivo de ejemplo y edítalo:

```bash
cp .env.example .env
nano .env
```

Rellena **OBLIGATORIAMENTE** estas 5 variables:

```env
# WhatsApp Business (Meta Cloud API)
WHATSAPP_TOKEN=TU_TOKEN_DE_ACCESO_PERMANENTE
PHONE_NUMBER_ID=123456789012345
WABA_ID=123456789012345

# Groq AI (modelo llama-3.3-70b)
GROQ_API_KEY=gsk_tuClaveDeGroqAqui

# Negocio
BUSINESS_NAME=Nombre del Negocio
BUSINESS_TYPE=peluquería
```

### 📖 Explicación de cada variable

| Variable | Obligatoria | Descripción |
|---|---|---|
| `WHATSAPP_TOKEN` | ✅ SÍ | Token de acceso permanente de Meta. Se genera en Meta for Developers. |
| `PHONE_NUMBER_ID` | ✅ SÍ | ID del número de WhatsApp Business (15 dígitos). |
| `WABA_ID` | ✅ SÍ | ID de la cuenta de WhatsApp Business. |
| `GROQ_API_KEY` | ✅ SÍ | Clave de API de Groq. Se obtiene gratis en console.groq.com. |
| `BUSINESS_NAME` | Opcional | Nombre del negocio (por defecto: "Peluquería WinoWin"). |
| `BUSINESS_TYPE` | Opcional | Tipo de negocio. Afecta al prompt del sistema. |

### 🔑 Cómo conseguir el token de Meta (paso a paso)

1. **Entra en Meta for Developers:** https://developers.facebook.com/
2. **Crea una app de tipo "Business"** (si no la tienes ya).
3. **Añade el producto "WhatsApp"** a tu app.
4. **Configura WhatsApp Business:**
   - Ve a "Configuración de WhatsApp" dentro de tu app.
   - Sigue el asistente: añade número de teléfono, verifica, configura perfil de empresa.
5. **Genera un token de acceso permanente:**
   - Ve a "Configuración de la app" > "Acceso a la API".
   - Genera un token con los permisos: `whatsapp_business_messaging`, `whatsapp_business_management`.
   - ⚠️ Usa el endpoint de intercambio para convertir el token temporal en permanente:
     ```
     GET https://graph.facebook.com/v22.0/oauth/access_token
       ?grant_type=fb_exchange_token
       &client_id={APP_ID}
       &client_secret={APP_SECRET}
       &fb_exchange_token={TOKEN_TEMPORAL}
     ```
6. **Obtén el PHONE_NUMBER_ID:**
   - Ve a "Configuración de WhatsApp" > "Números de teléfono".
   - Copia el ID del número (formato: `123456789012345`).
7. **Obtén el WABA_ID:**
   - En la misma pantalla, busca "ID de cuenta de WhatsApp Business" (formato: `123456789012345`).

### 🔑 Cómo conseguir la clave de Groq

1. Ve a https://console.groq.com/
2. Regístrate (gratis, con Google o email).
3. Ve a "API Keys".
4. Crea una nueva clave y cópiala.
5. La capa gratuita permite ~30 peticiones por minuto — suficiente para un negocio pequeño.

---

## 🌐 4. Configurar el túnel o dominio

### Opción A: ngrok (desarrollo / pruebas)

```bash
# Instalar ngrok
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null
echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | sudo tee /etc/apt/sources.list.d/ngrok.list
sudo apt update && sudo apt install ngrok

# Autenticar (necesitas cuenta gratuita en ngrok.com)
ngrok config add-authtoken TU_TOKEN_DE_NGROK

# Lanzar túnel (en otra terminal o como servicio)
ngrok http 8000
```

La URL de ngrok será algo como `https://abc123.ngrok-free.dev`. Apúntala.

### Opción B: Dominio propio con Nginx (producción)

```bash
# Instalar nginx
sudo apt install -y nginx

# Configurar proxy reverso
sudo nano /etc/nginx/sites-available/chatbot
```

```nginx
server {
    listen 80;
    server_name tudominio.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
# Activar sitio
sudo ln -s /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# SSL con Certbot (Let's Encrypt)
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d tudominio.com
```

---

## ✅ 5. Verificar el webhook en Meta

1. Ve a Meta for Developers > Tu App > WhatsApp > Configuración.
2. En **"URL de devolución de llamada"** (webhook callback URL), pega:
   ```
   https://tudominio.com/webhook
   ```
   (o la URL de ngrok si estás en desarrollo)
3. En **"Token de verificación"**, escribe:
   ```
   winowin_recepcionista_2026
   ```
4. Marca la casilla **"messages"** para suscribirte a eventos de mensajes.
5. Haz clic en **"Verificar y guardar"**.

> ✅ Si todo sale bien, Meta confirmará la verificación. Si falla:
> - Revisa que el servidor esté accesible desde Internet (prueba con `curl https://tudominio.com/webhook?hub.mode=subscribe&hub.challenge=test&hub.verify_token=winowin_recepcionista_2026`).
> - Revisa que no haya firewall bloqueando el puerto 8000.
> - Comprueba los logs del servidor.

---

## 🚀 6. Arrancar como servicio (systemd)

Para que el chatbot se ejecute automáticamente al iniciar el servidor y se reinicie si falla:

```bash
sudo nano /etc/systemd/system/chatbot-recepcionista.service
```

```ini
[Unit]
Description=WinoWin Recepcionista - Chatbot WhatsApp Business
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/chatbot-recepcionista
Environment=PATH=/opt/chatbot-recepcionista/venv/bin:/usr/bin
ExecStart=/opt/chatbot-recepcionista/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Activar e iniciar el servicio
sudo systemctl daemon-reload
sudo systemctl enable chatbot-recepcionista
sudo systemctl start chatbot-recepcionista

# Verificar estado
sudo systemctl status chatbot-recepcionista

# Ver logs en tiempo real
sudo journalctl -u chatbot-recepcionista -f
```

---

## 🩺 7. Verificar que todo funciona

```bash
# Health check
curl http://localhost:8000/

# Dashboard
curl http://localhost:8000/dashboard

# Test de chat (simulado)
curl "http://localhost:8000/api/test-chat?msg=¿Cuánto cuesta un alisado brasileño?"

# Ver disponibilidad (hoy)
curl "http://localhost:8000/api/availability"

# Ver citas de hoy
curl "http://localhost:8000/api/appointments"
```

---

## 📁 8. Estructura de archivos relevante

```
/opt/chatbot-recepcionista/
├── app/
│   ├── main.py              ← FastAPI: webhook + endpoints
│   ├── config.py             ← Lee .env y expone Config
│   ├── database.py           ← SQLite: mensajes, citas, servicios
│   ├── webhook_handler.py    ← Pipeline de procesamiento
│   ├── groq_client.py        ← Cliente Groq (IA)
│   ├── prompts.py            ← Prompt del sistema
│   ├── whatsapp_client.py    ← Cliente WhatsApp Cloud API
│   ├── conversation_state.py ← Máquina de estados (Fase 7)
│   └── context_manager.py    ← Gestión de contexto (Fase 7)
├── data/
│   └── chatbot.db            ← Base de datos SQLite
├── docs/
│   ├── README_CLIENTE.md     ← Manual para el cliente
│   ├── SETUP_TECNICO.md      ← Este archivo
│   └── CONFIG_NEGOCIO.md     ← Guía de personalización
├── .env                      ← Variables de entorno (NO SUBIR A GIT)
├── .env.example              ← Plantilla de .env
├── requirements.txt
└── README.md
```

---

## ⚠️ Notas importantes

- **El token de Meta actual es de una cuenta de desarrollo personal.** El cliente debe crear su propia cuenta de Meta Business y generar su propio token.
- **NUNCA** subas el archivo `.env` a Git. Está en `.gitignore`.
- Los mensajes de atención al cliente en WhatsApp son **gratuitos** (0€). Solo los mensajes de marketing tienen coste.
- La capa gratuita de Groq permite ~30 peticiones/minuto y ~1,000 peticiones/día. Para un negocio pequeño, esto es más que suficiente.
- Si el chatbot no envía respuestas, revisa que Meta no haya bloqueado la cuenta. En desarrollo, Meta exige método de pago y verificación de empresa incluso para mensajes de prueba.

---

## 🔄 Actualización y mantenimiento

```bash
# Actualizar código
cd /opt/chatbot-recepcionista
git pull

# Actualizar dependencias
source venv/bin/activate
pip install -r requirements.txt

# Reiniciar servicio
sudo systemctl restart chatbot-recepcionista
```

**Backup de la base de datos (recomendado: diario):**
```bash
cp /opt/chatbot-recepcionista/data/chatbot.db /backup/chatbot-$(date +%Y%m%d).db
```

---

*Documentación técnica · WinoWin Recepcionista v1.0*
