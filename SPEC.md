# ESPECIFICACION TECNICA - Bot Jacks
## Bot de venta de items via creditos en Telegram

---

## 1. DESCRIPCION GENERAL

Bot de Telegram para la gestion de venta de items digitales mediante un sistema de creditos. Los usuarios se registran, compran creditos via contacto manual con el owner, y canjean esos creditos por items del stock. Los administradores gestionan stock, creditos de usuarios, y envian anuncios masivos.

**Stack tecnologico:**
- Python 3.11
- python-telegram-bot v20+
- SQLite3 (base de datos local)
- Docker + Docker Compose (despliegue)

---

## 2. CONFIGURACION Y VARIABLES DE ENTORNO

Toda la configuracion sensible se lee desde archivo `.env` (nunca hardcodeado):

| Variable | Tipo | Descripcion |
|----------|------|-------------|
| `TELEGRAM_BOT_TOKEN` | string | Token del bot de BotFather |
| `ADMIN_IDS` | lista int | IDs de Telegram de admins separados por comas (ej: `123,456`) |
| `LOG_GROUP_ID` | int | ID del grupo/canal donde se loguean eventos (registro, recargas) |
| `CHANNEL_URL` | string | URL del canal de anuncios publico |
| `OWNER_USERNAME` | string | Username del owner para contacto (ej: `@Slashhhomeback`) |

**Seguridad:** El archivo `.env` esta en `.gitignore`. El repo publico solo contiene `.env.example` como plantilla.

---

## 3. BASE DE DATOS (SQLite3)

Tres tablas principales:

### 3.1 Tabla `users`
```sql
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,        -- Telegram User ID como string
    name TEXT,                  -- first_name del usuario
    username TEXT,              -- @username o "sin_username"
    credits INTEGER DEFAULT 0   -- Creditos disponibles
)
```

### 3.2 Tabla `stock`
```sql
CREATE TABLE IF NOT EXISTS stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item TEXT                   -- Cada fila es un item individual
)
```
**Nota:** Cada item es una fila independiente. Si quieres 100 cuentas, insertas 100 filas.

### 3.3 Tabla `history`
```sql
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,               -- ID del comprador
    cantidad INTEGER,           -- Cuantos items compro
    items TEXT,                 -- Items entregados (multilinea, separados por \n)
    fecha DATETIME DEFAULT (datetime('now', 'localtime')),
    compra_id TEXT              -- ID aleatorio de 6 digitos (100000-999999)
)
```
**Migracion legacy:** Si la tabla existe sin `compra_id`, se ejecuta `ALTER TABLE` automaticamente al arrancar.

### 3.4 Concurrencia
- `PRAGMA journal_mode=WAL` activado para reducir bloqueos SQLite.
- `check_same_thread=False` porque python-telegram-bot maneja multihilo.
- **Advertencia:** SQLite no es 100% thread-safe para escrituras concurrentes. Para alto trafico, migrar a PostgreSQL.

---

## 4. SISTEMA DE PERMISOS

- **Usuario normal:** Cualquier persona que hable con el bot.
- **Admin:** UID debe estar en la lista `ADMIN_IDS` (variable de entorno). Todas las funciones admin verifican `is_admin(uid)` al inicio.

---

## 5. FLUJOS DE COMANDO (PASO A PASO)

### 5.1 /start
**Quien:** Cualquier usuario
**Flujo:**
1. Responde con mensaje de bienvenida fijo.
2. Invita a `/register` y `/cmds`.

### 5.2 /register
**Quien:** Cualquier usuario no registrado
**Flujo:**
1. Obtiene `effective_user` (id, first_name, username).
2. Verifica si `user.id` ya existe en tabla `users`.
3. Si existe → responde "Ya estas registrado" (intenta enviar foto `imagen/Bienvenida.jpeg`, fallback a texto).
4. Si no existe → INSERT en `users` con credits=0.
5. Responde al usuario con mensaje de confirmacion (foto o texto).
6. **Logueo:** Envio asincrono de mensaje al `LOG_GROUP_ID` con los datos del nuevo usuario. Si falla, solo imprime error en consola (no interrumpe el flujo).

**Datos almacenados:** id (string), name, username, credits=0.

### 5.3 /me
**Quien:** Usuario registrado
**Flujo:**
1. Busca al usuario por su `effective_user.id` en `users`.
2. Si no existe → "Usa /register primero".
3. Si existe → muestra nombre, username, ID, creditos y stock disponible global (COUNT de tabla `stock`).
4. Intenta adjuntar foto `imagen/Estadisticas.jpeg`, fallback a texto.

### 5.4 /buy
**Quien:** Cualquier usuario
**Flujo:**
1. Muestra precios hardcodeados: 7$ = 5 creditos, 12$ = 10 creditos.
2. Muestra stock disponible global.
3. Botones inline: enlace al canal de anuncios + enlace al owner para recargar.
4. No realiza ninguna transaccion ni verificacion de creditos.

### 5.5 /comprar <cantidad>
**Quien:** Usuario registrado
**Flujo:**
1. Verifica que el usuario este registrado.
2. Valida argumento: debe ser digito, mayor a 0.
3. Lee creditos actuales del usuario. Si `creditos < cantidad` → muestra boton de contacto al owner.
4. Lee de `stock` LIMIT cantidad (los primeros items disponibles).
5. Si `len(items) < cantidad` → "No hay stock suficiente".
6. **TRANSACCION ATOMICA (BEGIN/COMMIT/ROLLBACK):**
   - Borra los items de `stock` (DELETE WHERE id IN placeholders).
   - Descuenta creditos del usuario (UPDATE credits = credits - cantidad).
   - Inserta en `history` con `compra_id` generado aleatorio.
   - COMMIT. Si falla cualquier paso → ROLLBACK.
7. Responde al usuario con: ID de compra, cantidad, items entregados, creditos restantes.
8. Intenta adjuntar foto `imagen/Generando.jpeg`, fallback a texto.

**Nota de seguridad:** La operacion de DELETE usa placeholders `?` parametrizados. Versiones previas tenian SQL injection por concatenacion de IDs.

### 5.6 /historia
**Quien:** Usuario registrado
**Flujo:**
1. Lee todas las filas de `history` WHERE user_id = uid, orden DESC.
2. Si no hay filas → "No has realizado ninguna compra".
3. Formatea cada compra con: compra_id (o fallback a #db_id), fecha, cantidad, items.
4. Si el texto total <= 1024 chars → intenta enviar con foto `Estadisticas.jpeg`.
5. Si supera 1024 chars → envia como texto plano dividido en chunks de 4000 chars (limite de Telegram = 4096).

### 5.7 /cmds
**Quien:** Cualquier usuario
**Flujo:**
1. Detecta si el usuario es admin (`is_admin`).
2. Muestra lista de comandos usuario o lista extendida admin.

---

## 6. COMANDOS ADMINISTRADOR

### 6.1 /stock <texto>
**Quien:** Admin
**Flujo:**
1. Verifica permiso admin.
2. Valida que haya argumentos (el texto del item).
3. INSERT en tabla `stock` una sola fila con el texto proporcionado.
4. Responde con stock actual total.

**Uso real:** Si tienes 50 cuentas, ejecutas `/stock cuenta1`, `/stock cuenta2`... 50 veces. Cada fila es un item individual.

### 6.2 /resetstock
**Quien:** Admin
**Flujo:**
1. Verifica admin.
2. Ejecuta `DELETE FROM stock` (borra todo).
3. COMMIT.
4. Confirma "Stock reiniciado".

**Sin confirmacion ni backup.** Accion destructiva directa.

### 6.3 /addcred <ID> <cantidad>
**Quien:** Admin
**Flujo:**
1. Verifica admin.
2. Valida 2 argumentos. Segundo debe ser digito.
3. Verifica que el usuario exista en `users`.
4. UPDATE `users.credits = credits + cantidad`.
5. Responde con ID, cantidad agregada, total actual.
6. **Logueo:** Mensaje al `LOG_GROUP_ID` con nombre, ID, username, creditos agregados, total actual, y ID del admin que ejecuto.

### 6.4 /delcred <ID> <cantidad>
**Quien:** Admin
**Flujo:**
1. Verifica admin.
2. Valida argumentos. Segundo digito.
3. Verifica usuario existe.
4. Lee creditos actuales.
5. Calcula `new_credits = max(old - cantidad, 0)` (nunca baja de 0).
6. UPDATE y confirma con antes/después.

### 6.5 /compras <@usuario | ID>
**Quien:** Admin
**Flujo:**
1. Verifica admin.
2. Valida argumento.
3. Busca usuario por funcion `buscar_usuario_por_arg()`:
   - Si empieza con `@` → busca por `lower(username)`.
   - Si no → busca por `id` exacto.
4. Si no encuentra → "Usuario no registrado".
5. Lee `history` del usuario orden DESC.
6. Formatea historial completo dividido en chunks de 4000 chars si es largo.

### 6.6 /info [ID | @usuario]
**Quien:** Admin
**Flujo:**
1. Verifica admin.
2. Tres modos de entrada:
   - Si responde a un mensaje (`reply_to_message`) → usa el ID del autor del mensaje respondido.
   - Si hay argumento → busca por `buscar_usuario_por_arg()`.
   - Si no hay nada → muestra uso correcto.
3. Muestra: nombre, username, ID, creditos, total de compras realizadas.

### 6.7 /anuncio [texto | respuesta a mensaje]
**Quien:** Admin
**Flujo masivo de broadcast:**
1. Verifica admin.
2. Carga lista de todos los IDs registrados en `users`.
3. **Modo A - Responder a mensaje:**
   - Copia el mensaje original a cada usuario via `copy_message`.
   - Mantiene formato, emojis premium, multimedia original.
   - Boton inline al canal.
4. **Modo B - Texto directo o foto+caption:**
   - Si el mensaje tiene foto+caption → envia foto con caption formateada + boton.
   - Si es solo texto → envia mensaje de texto + boton.
   - Caption procesada: elimina `/anuncio` del texto si viene en caption.
5. Cuenta enviados/fallidos (excepciones silenciadas, no interrumpen broadcast).
6. Responde al admin con resumen: enviados/fallidos.

**Limitaciones:** No hay rate-limiting. Si hay 1000+ usuarios, Telegram puede banear temporalmente por flood. Broadcast secuencial sin delay.

---

## 7. FUNCIONES AUXILIARES

| Funcion | Descripcion |
|---------|-------------|
| `is_admin(uid)` | Verifica si uid esta en `ADMIN_IDS` (lista cargada de `.env`) |
| `stock_count()` | `SELECT COUNT(*) FROM stock` |
| `gen_id()` | `random.randint(100000, 999999)` como string |
| `buscar_usuario_por_arg(arg)` | Normaliza `@` → busca por username lowercase; sino por ID exacto. Retorna tupla completa del usuario. |
| `error_handler()` | Handler global: solo imprime `context.error` en consola. |

---

## 8. ESTRUCTURA DE ARCHIVOS DEL PROYECTO

```
bot-jacks/
├── .env                    # No se sube a GitHub
├── .env.example            # Plantilla para nuevos despliegues
├── .gitignore              # Ignora .env, bot.db, datos de usuario
├── bot.py                  # Codigo principal del bot
├── bot.db                  # SQLite (no se sube a GitHub)
├── requirements.txt        # python-telegram-bot, python-dotenv
├── Dockerfile              # Python 3.11-slim, instala deps, ejecuta bot.py
├── docker-compose.yml      # Servicio "bot", monta bot.db e imagen/ como volumenes
├── README.md               # Instrucciones de despliegue
├── SPEC.md                 # Este documento
├── imagen/
│   ├── Bienvenida.jpeg     # Usada en /register y /start
│   ├── Estadisticas.jpeg   # Usada en /me y /historia
│   └── Generando.jpeg      # Usada en /comprar
└── (archivos legacy JSON, ignorados por git)
    ├── users.json
    ├── groups.json
    ├── usuarios_actualizados.json
    ├── orders.txt
    └── stock.txt
```

---

## 9. DESPLIEGUE CON DOCKER

### Construccion
```bash
docker compose up -d --build
```

### Volumenes montados
- `./bot.db:/app/bot.db` → Persistencia de base de datos entre reinicios/contenedores
- `./imagen:/app/imagen` → Carpeta de imagenes

### Variables
- El contenedor lee `.env` via `env_file` en docker-compose.

---

## 10. SEGURIDAD Y BUGS CORREGIDOS

| Problema | Estado |
|----------|--------|
| Token hardcodeado en codigo | **Corregido** → lee de `.env` |
| SQL Injection en `DELETE FROM stock WHERE id IN (...)` | **Corregido** → usa placeholders `?` |
| Transaccion no atomica en `/comprar` (podia perder stock sin descontar creditos) | **Corregido** → BEGIN/ROLLBACK/COMMIT |
| Asyncio loop incompatible Linux/Docker | **Corregido** → eliminado codigo Windows-only |
| base de datos en GitHub | **Protegido** → `.gitignore` |

---

## 11. LIMITACIONES CONOCIDAS Y NOTAS PARA EL PROGRAMADOR

1. **No hay panel web:** Toda la gestion es via comandos Telegram. Para scale, considerar panel web (Flask/FastAPI).
2. **Broadcast sin rate limit:** `/anuncio` envia mensajes secuencialmente sin delay. Riesgo de rate-limit de Telegram en listas grandes. Considerar cola con Celery/Redis.
3. **SQLite threading:** `check_same_thread=False` permite multihilo pero puede haber "database is locked" en alta concurrencia. WAL mode mitiga pero no elimina.
4. **No hay backup automatico:** `bot.db` se respalda manualmente o por cron en el host.
5. **Precios hardcodeados:** Los precios estan en el string de `/buy`. Para cambiarlos hay que editar codigo y redeploy.
6. **No hay sistema de pagos automatico:** Las recargas son manuales (admin ejecuta `/addcred` tras recibir pago externo).
7. **Stock individual por fila:** Cada item es una fila SQL. No hay tabla de "productos" con cantidad. Esto es intencional para entregar items unicos (cuentas, keys, etc.).
8. **Imagenes locales:** Las fotos se leen del filesystem local (`open("imagen/...")`). En Docker funcionan porque se monta el volumen `imagen/`.
9. **No hay tests unitarios:** El bot no tiene suite de pruebas. Cualquier refactor requiere testing manual en Telegram.
10. **Manejo de errores basico:** `error_handler` solo imprime a consola. No hay notificacion de errores criticos a admin.

---

## 12. IDEAS DE MEJORAS FUTURAS (fuera de scope actual)

- Panel web admin (FastAPI + HTML simple) para gestionar stock y usuarios sin Telegram.
- Sistema de pagos automatico (Stripe, crypto, etc.) para recargas sin intervencion manual.
- Rate limiting en broadcast con cola de tareas (Celery/Redis/RQ).
- Backup automatico de `bot.db` a S3/Google Drive via cron.
- Tabla de productos/categorias con stock agrupado en vez de filas individuales.
- Tests unitarios con pytest y mocks de python-telegram-bot.
- Webhook mode en vez de polling (mejor para produccion con alto trafico).
- Logging estructurado a archivo en vez de print() a consola.

---

**Documento generado:** Abril 2026
**Version bot:** 1.0 (post-refactor env+docker)
**Autor especificacion:** Hugo (Bot Jacks)
