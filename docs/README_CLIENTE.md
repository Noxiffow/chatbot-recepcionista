# 🤖 WinoWin Recepcionista — Manual para el Cliente

> **Bienvenido/a a tu nuevo recepcionista virtual.**  
> Este manual te explica qué hace tu chatbot, qué necesitas para usarlo y cómo gestionarlo día a día.  
> Está escrito en lenguaje llano, sin tecnicismos. Si sabes usar WhatsApp y un navegador web, puedes manejar esto.

---

## 📋 ¿Qué hace tu recepcionista virtual?

Imagina que tienes a una persona atendiendo tu WhatsApp de empresa las 24 horas del día, los 7 días de la semana. Eso es lo que hace este chatbot:

- **Responde automáticamente** a los mensajes que te llegan por WhatsApp Business.
- **Informa sobre tus servicios y precios** a quien pregunte (sin errores, siempre con los datos actualizados).
- **Gestiona las citas** — comprueba tu agenda en tiempo real, le dice al cliente qué días y horas tienes libres, y reserva la cita.
- **Deriva a una persona** cuando un cliente necesita hablar con un humano (por ejemplo, una queja o una consulta compleja).
- **Recuerda de qué hablaste** con cada cliente, incluso si la conversación dura varios días.

Todo esto funciona **de forma automática**, sin que tengas que estar pendiente del móvil.

---

## 🛒 ¿Qué necesitas para tenerlo funcionando?

Para que tu recepcionista virtual funcione, necesitas 4 cosas. No te preocupes, te las explico una a una:

### 1. Una cuenta de Meta Business verificada

**¿Qué es?** Es la cuenta de empresa que te pide Meta (la empresa dueña de WhatsApp, Facebook e Instagram) para usar WhatsApp Business de forma profesional.

**¿Para qué sirve?** Es como el "DNI de tu empresa" en WhatsApp. Sin esto, Meta no te deja usar un chatbot automático.

**¿Cómo lo consigues?** Tienes que:
- Tener una cuenta de Facebook Business (gratis).
- Crear una "app" dentro de Meta for Developers (es un panel de control, no hace falta programar nada).
- Verificar tu empresa (Meta te pide documentos como el CIF, una factura de teléfono, etc.).

> ⚠️ **Ojo:** Este paso puede tardar unos días. Empieza por aquí cuanto antes. Si necesitas ayuda, pídesela a la persona que te está instalando el chatbot.

### 2. Un número de WhatsApp Business

**¿Qué es?** El número de teléfono desde el que hablará tu chatbot con los clientes.

**Importante:** 
- Debe ser un número que **no esté ya registrado en WhatsApp** (ni en el WhatsApp normal ni en WhatsApp Business).
- Puede ser un número nuevo o uno que liberes (borrando la cuenta de WhatsApp asociada).
- Recomendación: compra una SIM nueva de prepago (~5-10€) solo para esto.

### 3. Un método de pago configurado en Meta

**¿Qué es?** Una tarjeta de crédito o débito que añades a tu cuenta de Meta Business.

**¿Por qué?** Aunque los mensajes de atención al cliente son **gratis** (0€), Meta te pide una tarjeta para verificar que eres una empresa real. Es como la tarjeta que te piden en un hotel — no te van a cobrar nada, pero la necesitan tener.

> 💡 **Coste real:** Las conversaciones de atención al cliente en WhatsApp Business cuestan **0€**. Solo pagarías si enviaras mensajes de marketing masivo (lo cual probablemente no harás).

### 4. Un servicio de alojamiento

**¿Qué es?** Un ordenador que está siempre encendido para que tu chatbot no se "duerma".

**¿Cuánto cuesta?** Entre 5€ y 10€ al mes (como una suscripción a Netflix).

**¿Cómo se consigue?** La persona que te instale el chatbot lo contratará por ti. Es algo que se hace una vez y te olvidas.

---

## ✏️ Cómo cambiar tus servicios y precios

Tus servicios y precios están guardados en un archivo sencillo que puedes editar sin tocar nada de programación.

**Dónde está:** En la carpeta `data/` de tu chatbot hay un archivo que se llama `servicios.json`. Se ve así:

```json
[
  {
    "nombre": "Alisado Brasileño Corto",
    "categoria": "Alisados",
    "precio": 85,
    "duracion_minutos": 120,
    "descripcion": "Ideal para pelo corto. Resultado natural sin encrespamiento."
  },
  {
    "nombre": "Alisado Brasileño Largo",
    "categoria": "Alisados",
    "precio": 120,
    "duracion_minutos": 180,
    "descripcion": "Para melenas largas. Efecto liso duradero con keratina."
  }
]
```

**Para cambiar algo:**
1. Abre el archivo con cualquier editor de texto (el Bloc de Notas del ordenador sirve).
2. Cambia el precio, el nombre, o añade un servicio nuevo copiando y pegando el formato.
3. Guarda el archivo.
4. Pídele a tu técnico que "reinicie el chatbot" (son 10 segundos).

**Lo que NO debes hacer:**
- No cambies las comillas ni los corchetes. Respeta el formato.
- Si no te sientes seguro, pídele al técnico que lo haga. Son 2 minutos.

---

## 📊 Cómo ver las citas y los mensajes

Tu chatbot incluye un panel de control al que puedes acceder desde cualquier navegador (Chrome, Firefox, Safari, Edge).

**Dirección del panel:** `http://[dirección-de-tu-servidor]/dashboard`

Por ejemplo: `http://192.168.1.50/dashboard` o `http://tu-dominio.com/dashboard`

**Qué puedes ver en el panel:**
- 📨 **Los últimos mensajes** que han entrado y las respuestas que ha dado el chatbot.
- 📊 **Estadísticas:** cuántos mensajes ha recibido, cuántas conversaciones activas hay.
- 📅 **Las citas del día** y la disponibilidad de la agenda.

**Para ver las citas:** En la misma web, visita `/api/appointments` para ver todas las citas agendadas.

> 💡 Si algún día ves algo raro (una respuesta que no cuadra, un cliente enfadado), puedes intervenir tú mismo respondiendo desde tu WhatsApp. El chatbot lo detectará y no se meterá.

---

## ❓ Preguntas frecuentes (FAQ)

### ¿Puedo usar mi WhatsApp personal mientras el chatbot está funcionando?

**Sí.** El chatbot usa su propio número de WhatsApp Business, distinto al tuyo. Tú sigues usando tu WhatsApp normal como siempre.

### ¿El chatbot se equivoca alguna vez?

Es muy raro, pero posible. El chatbot usa inteligencia artificial avanzada, pero no es una persona. Si ves que responde algo extraño, avisa al técnico para ajustar el "tono" de las respuestas. Se arregla en minutos.

### ¿Qué pasa si hay un apagón o se va Internet?

Si el ordenador que aloja el chatbot se apaga, los mensajes de WhatsApp **no se pierden**. WhatsApp los guarda hasta 24 horas. Cuando el chatbot vuelva a encenderse, los procesará todos.

### ¿Puedo cambiar el nombre del negocio o el horario?

Sí. Son opciones sencillas en un archivo de configuración. Pídeselo al técnico (es un cambio de 2 minutos).

### ¿Cuánto cuesta mantener esto?

- **Alojamiento:** 5-10€ al mes.
- **Mensajes de WhatsApp:** 0€ para atención al cliente.
- **IA (inteligencia artificial):** La capa gratuita de Groq (que es el "cerebro" del chatbot) es más que suficiente para una peluquería o negocio pequeño.
- **Total:** Entre 5€ y 10€ al mes.

### ¿Qué pasa si quiero dejar de usarlo?

Nada. Cancelas el servicio de alojamiento y listo. Tus datos de clientes están en tu poder (en una base de datos SQLite que puedes abrir con programas gratuitos).

### ¿Necesito saber de programación o informática?

**No.** Para el día a día solo necesitas saber usar WhatsApp y un navegador web. Para los cambios de precio o servicios, con seguir este manual te basta. Y si algo se complica, siempre puedes llamar al técnico.

---

## 📞 Soporte

Si tienes cualquier duda, contacta con la persona que te instaló el chatbot:

- **Técnico responsable:** [Nombre del técnico]
- **Teléfono:** [Teléfono]
- **Email:** [Email]

---

> *WinoWin Recepcionista v1.0 · Hecho con ❤️ para que tú no tengas que estar pegado al móvil.*
