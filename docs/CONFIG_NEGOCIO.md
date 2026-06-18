# ⚙️ Configuración del Negocio — WinoWin Recepcionista

> Cómo personalizar el chatbot para tu negocio sin tocar código.  
> Para todos los cambios aquí descritos, solo necesitas editar archivos de texto o la base de datos.

---

## 🏷️ 1. Nombre del negocio

El nombre del negocio aparece en el saludo y en el panel de control.

**Dónde se cambia:** Archivo `.env` en la raíz del proyecto.

```env
BUSINESS_NAME=Mi Negocio
BUSINESS_TYPE=peluquería
```

| Variable | Descripción | Ejemplos |
|---|---|---|
| `BUSINESS_NAME` | Nombre del negocio | `Peluquería Ana`, `Taller López` |
| `BUSINESS_TYPE` | Tipo de negocio (influye en el prompt) | `peluquería` |

> Después de cambiar, reinicia el servicio: `sudo systemctl restart chatbot-recepcionista`

---

## 💇 2. Servicios y precios

Los servicios que ofrece el negocio están en la base de datos SQLite. Se pueden gestionar de dos formas:

### Opción A: Insertar directamente en la BD (recomendado)

```bash
# Conectar a la base de datos
cd /opt/chatbot-recepcionista
sqlite3 data/chatbot.db
```

```sql
-- Ver todos los servicios actuales
SELECT * FROM services;

-- Añadir un servicio nuevo
INSERT INTO services (name, category, price, duration_min, description)
VALUES ('Nombre del Servicio', 'Categoría', 85.00, 120, 'Descripción breve');

-- Modificar un precio
UPDATE services SET price = 95.00 WHERE id = 1;

-- Eliminar un servicio
DELETE FROM services WHERE id = 999;

-- Salir
.quit
```

### Opción B: Usar un script de importación (para muchos cambios)

Si prefieres editar un archivo CSV/JSON, puedes crear un archivo `servicios.csv`:

```csv
nombre,categoria,precio,duracion_min,descripcion
Alisado Brasileño Corto,Alisados,85,120,Ideal para pelo corto. Resultado natural.
Alisado Brasileño Medio,Alisados,100,150,Para melenas medias. Efecto liso duradero.
Alisado Brasileño Largo,Alisados,120,180,Para melenas largas. Keratina premium.
Corte de Puntas,Cortes,25,30,Corte de puntas básico.
Lavado y Peinado,Peinados,30,45,Lavado + secado + peinado.
Tinte sin Amoniaco,Tintes,55,90,Coloración respetuosa con el cabello.
```

Luego importa con el script auxiliar (incluido en `scripts/importar_servicios.py`).

### Estructura de la tabla `services`

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INTEGER | ID único (autonumérico) |
| `name` | TEXT | Nombre del servicio |
| `category` | TEXT | Categoría (ej: Alisados, Cortes, Tintes) |
| `price` | REAL | Precio en euros (ej: 85.0) |
| `duration_min` | INTEGER | Duración en minutos (ej: 120 para 2h) |
| `description` | TEXT | Descripción breve |

---

## 🕐 3. Horario de apertura

El horario de apertura determina cuándo el chatbot puede agendar citas.

**Dónde se cambia:** Archivo `app/database.py`, variable `BUSINESS_HOURS` (líneas ~445-453).

```python
BUSINESS_HOURS = {
    0: [(9, 14), (16, 20)],  # Lunes: 9:00-14:00, 16:00-20:00
    1: [(9, 14), (16, 20)],  # Martes
    2: [(9, 14), (16, 20)],  # Miércoles
    3: [(9, 14), (16, 20)],  # Jueves
    4: [(9, 14), (16, 20)],  # Viernes
    5: [(9, 14)],            # Sábado: 9:00-14:00
    6: [],                   # Domingo: cerrado
}
```

**Claves de días:**
| Número | Día |
|---|---|
| 0 | Lunes |
| 1 | Martes |
| 2 | Miércoles |
| 3 | Jueves |
| 4 | Viernes |
| 5 | Sábado |
| 6 | Domingo |

**Formato de horario:** Pares `(hora_inicio, hora_fin)` en formato 24h.

**Ejemplos de cambios:**

```python
# Abrir solo mañanas toda la semana
BUSINESS_HOURS = {
    0: [(9, 14)],  # Lunes a Viernes: solo mañanas
    1: [(9, 14)],
    2: [(9, 14)],
    3: [(9, 14)],
    4: [(9, 14)],
    5: [(10, 13)], # Sábado más corto
    6: [],         # Domingo cerrado
}

# Jornada partida solo L-V, cerrado finde
BUSINESS_HOURS = {
    0: [(8, 13), (16, 19)],  # L-V mañana y tarde
    1: [(8, 13), (16, 19)],
    2: [(8, 13), (16, 19)],
    3: [(8, 13), (16, 19)],
    4: [(8, 13), (16, 19)],
    5: [],  # Sábado cerrado
    6: [],  # Domingo cerrado
}
```

> ⚠️ Después de cambiar el horario, reinicia el servicio y regenera los slots de disponibilidad (se hace automáticamente al arrancar para los próximos 30 días).

### Duración de los bloques de agenda

Por defecto, cada bloque es de **30 minutos** (`SLOT_DURATION_MIN = 30`). Si un servicio dura 120 minutos, ocupará 4 bloques consecutivos. Puedes ajustar `SLOT_DURATION_MIN` en `database.py` si prefieres bloques de 15 o 60 minutos.

---

## 🧠 4. Personalidad y tono del chatbot (Prompt del sistema)

El prompt del sistema define cómo habla el recepcionista virtual: su tono, personalidad, reglas de negocio y forma de responder.

**Dónde se cambia:** Archivo `app/prompts.py`, variable `SYSTEM_PROMPT_TEMPLATE`.

### Plantilla por defecto (resumida)

```
Eres RECEPCIONISTA, un asistente virtual amable y profesional de {business_name}.
Eres una {business_type} especializada en ALISADOS profesionales...

## TU PERSONALIDAD
- Eres cálida, cercana y profesional.
- Respondes de forma concisa (2-4 frases).
- Usas emojis ocasionalmente.

## TUS FUNCIONES
1. Informar sobre servicios y precios.
2. Gestionar citas.
3. Resolver dudas frecuentes.
4. Derivar a un humano si es necesario.
```

### Qué puedes personalizar

| Sección | Qué cambias |
|---|---|
| **Tu personalidad** | El tono (más formal, más cercano, más técnico, etc.) |
| **Tus funciones** | Servicios que ofrece (añadir/quitar funciones) |
| **Información del negocio** | Dirección, teléfono, horario (texto informativo) |
| **Reglas importantes** | Comportamiento ante quejas, si puede o no dar descuentos, etc. |

### Ejemplos de adaptación por tipo de negocio

**Taller mecánico:**
```
Eres RECEPCIONISTA, asistente virtual de {business_name}.
Eres un taller mecánico multimarca especializado en diagnosis y reparación.

## TU PERSONALIDAD
- Eres directo, profesional y transmitiendo confianza.
- Evitas tecnicismos innecesarios con el cliente.
```

**Clínica dental:**
```
Eres RECEPCIONISTA, asistente virtual de {business_name}.
Eres una clínica dental con servicio de odontología general y estética.

## REGLAS IMPORTANTES
- SIEMPRE recuerda que NO eres un médico. Ante síntomas, deriva al odontólogo.
- NUNCA diagnostiques ni recomiendes tratamientos sin consultar.
```

> ⚠️ **Variables disponibles en el prompt:** `{business_name}`, `{business_type}`, `{catalog_text}`. Estas se reemplazan automáticamente con los valores reales.

---

## 🔄 5. Otros ajustes configurables (en .env o config.py)

```env
# Modelo de IA (Groq)
# Opciones: llama-3.3-70b-versatile, mixtral-8x7b-32768, gemma2-9b-it
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_MAX_TOKENS=512
GROQ_TEMPERATURE=0.7
```

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `GROQ_MODEL` | Modelo de IA de Groq | `llama-3.3-70b-versatile` |
| `GROQ_MAX_TOKENS` | Longitud máxima de respuesta | `512` |
| `GROQ_TEMPERATURE` | Creatividad (0.0 = preciso, 1.0 = creativo) | `0.7` |

---

## 📝 Resumen: qué archivo editar para cada cambio

| Cambio | Archivo | Requiere reinicio |
|---|---|---|
| Nombre del negocio | `.env` → `BUSINESS_NAME` | ✅ Sí |
| Servicios y precios | BD `data/chatbot.db` → tabla `services` | ❌ No |
| Horario de apertura | `app/database.py` → `BUSINESS_HOURS` | ✅ Sí |
| Personalidad / tono | `app/prompts.py` → `SYSTEM_PROMPT_TEMPLATE` | ✅ Sí |
| Modelo de IA | `.env` → `GROQ_MODEL` | ✅ Sí |
| Dirección / teléfono | `app/prompts.py` → sección "Información del negocio" | ✅ Sí |
| Duración de bloques | `app/database.py` → `SLOT_DURATION_MIN` | ✅ Sí |

---

*Guía de configuración · WinoWin Recepcionista v1.0*
