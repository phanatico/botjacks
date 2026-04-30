print("BOT INICIADO")

import os
import sqlite3
import random
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()

# ================= CONFIG =================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID", "0"))
CHANNEL = os.getenv("CHANNEL_URL", "")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "")

# ================= DB =================
db = sqlite3.connect("bot.db", check_same_thread=False)
db.execute("PRAGMA journal_mode=WAL;")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT,
    username TEXT,
    credits INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    cantidad INTEGER,
    items TEXT,
    fecha DATETIME DEFAULT (datetime('now', 'localtime')),
    compra_id TEXT
)
""")

try:
    cursor.execute("ALTER TABLE history ADD COLUMN compra_id TEXT")
except sqlite3.OperationalError:
    pass

db.commit()

# ================= HELPERS =================
def is_admin(uid):
    return uid in ADMIN_IDS

def stock_count():
    cursor.execute("SELECT COUNT(*) FROM stock")
    return cursor.fetchone()[0]

def gen_id():
    return str(random.randint(100000, 999999))

def buscar_usuario_por_arg(arg):
    arg = arg.strip()

    if arg.startswith("@"):
        username = arg.replace("@", "").lower()
        cursor.execute("""
            SELECT id, name, username, credits
            FROM users
            WHERE lower(username)=?
        """, (username,))
    else:
        cursor.execute("""
            SELECT id, name, username, credits
            FROM users
            WHERE id=?
        """, (arg,))

    return cursor.fetchone()

# ================= ERROR =================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("ERROR:", context.error)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
👋 Bienvenido

Usa /register para registrarte.
Usa /cmds para ver comandos.
""")

# ================= CMDS =================
async def cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if is_admin(uid):
        text = """
📜 COMANDOS ADMIN

👤 USUARIO:
/start - Inicia el bot
/register - Registra tu cuenta en el bot
/me - Muestra tu perfil, ID, @usuario, créditos y stock
/buy - Muestra precios, contacto y canal
/comprar 1 - Compra 1 item y descuenta 1 crédito
/comprar 2 - Compra 2 items y descuenta 2 créditos
/comprar 3 - Compra 3 items y descuenta 3 créditos
/historia - Muestra tu historial de compras

🛠 ADMIN:
/stock TEXTO - Agrega un item nuevo al stock
/resetstock - Borra todo el stock actual
/addcred ID 1 - Agrega 1 crédito a un usuario
/delcred ID 1 - Quita 1 crédito a un usuario
/anuncio TEXTO - Envía un anuncio a usuarios registrados
/compras @usuario - Ver historial de compras de un usuario
/compras ID - Ver historial de compras por ID
/info ID - Ver info y créditos de un usuario
/info @usuario - Ver info y créditos por @usuario
/info - Responde a un mensaje con /info para ver info del usuario
"""
    else:
        text = """
📜 COMANDOS USUARIO

/start - Inicia el bot
/register - Registra tu cuenta en el bot
/me - Muestra tu perfil, ID, @usuario, créditos y stock
/buy - Muestra precios, contacto y canal
/comprar 1 - Compra 1 item y descuenta 1 crédito
/comprar 2 - Compra 2 items y descuenta 2 créditos
/comprar 3 - Compra 3 items y descuenta 3 créditos
/historia - Muestra tu historial de compras

💡 1 crédito = 1 item
"""

    await update.message.reply_text(text)

# ================= REGISTER =================
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    uid = str(user.id)
    name = user.first_name or "Usuario"
    username = user.username if user.username else "sin_username"

    cursor.execute("SELECT id FROM users WHERE id=?", (uid,))
    if cursor.fetchone():
        try:
            await update.message.reply_photo(photo=open("imagen/Bienvenida.jpeg", "rb"), caption="⚠️ Ya estás registrado")
        except FileNotFoundError:
            await update.message.reply_text("⚠️ Ya estás registrado")
        return

    cursor.execute(
        "INSERT INTO users (id, name, username, credits) VALUES (?, ?, ?, ?)",
        (uid, name, username, 0)
    )
    db.commit()

    texto_bienvenida = f"""
✅ REGISTRADO

👤 Nombre: {name}
🆔 ID: {uid}
📛 Usuario: @{username}
💰 Créditos: 0
"""
    try:
        await update.message.reply_photo(photo=open("imagen/Bienvenida.jpeg", "rb"), caption=texto_bienvenida)
    except FileNotFoundError:
        await update.message.reply_text(texto_bienvenida)

    try:
        await context.bot.send_message(
            LOG_GROUP_ID,
            f"""
🆕 NUEVO USUARIO

👤 Nombre: {name}
🆔 ID: {uid}
📛 Usuario: @{username}
💰 Créditos: 0
"""
        )
    except Exception as e:
        print("Error log register:", e)

# ================= ME =================
async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)

    cursor.execute("SELECT name, username, credits FROM users WHERE id=?", (uid,))
    user = cursor.fetchone()

    if not user:
        await update.message.reply_text("⚠️ Usa /register primero")
        return

    texto_perfil = f"""
👤 PERFIL

👤 Nombre: {user[0]}
📛 Usuario: @{user[1]}
🆔 ID: {uid}
💰 Créditos: {user[2]}
📦 Stock: {stock_count()}
"""
    try:
        await update.effective_message.reply_photo(photo=open("imagen/Estadisticas.jpeg", "rb"), caption=texto_perfil)
    except FileNotFoundError:
        await update.effective_message.reply_text(texto_perfil)

# ================= BUY =================
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("📢 Canal de anuncios", url=CHANNEL)],
        [InlineKeyboardButton("💬 Contactar para recargar", url=f"https://t.me/{OWNER_USERNAME.replace('@', '')}")]
    ]

    await update.message.reply_text(f"""
💰 PRECIOS

7$ = 5 créditos
12$ = 10 créditos

⚠️ Por cada cuenta se descuenta un crédito.

📩 Para recargar contacta:
👉 {OWNER_USERNAME}

📦 Stock disponible: {stock_count()}
""", reply_markup=InlineKeyboardMarkup(kb))

# ================= STOCK =================
async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ No tienes permiso.\nUsa /cmds")
        return

    if not context.args:
        await update.message.reply_text("Uso correcto:\n/stock TEXTO")
        return

    item = " ".join(context.args)

    cursor.execute("INSERT INTO stock (item) VALUES (?)", (item,))
    db.commit()

    await update.message.reply_text(f"""
✅ Stock agregado

📦 Stock actual: {stock_count()}
""")

# ================= RESET STOCK =================
async def resetstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ No tienes permiso.\nUsa /cmds")
        return

    cursor.execute("DELETE FROM stock")
    db.commit()

    await update.message.reply_text("✅ Stock reiniciado")

# ================= ADD CREDIT =================
async def addcred(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ No tienes permiso.\nUsa /cmds")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Uso correcto:\n/addcred ID CANTIDAD")
        return

    uid = context.args[0]

    if not context.args[1].isdigit():
        await update.message.reply_text("❌ La cantidad debe ser un número")
        return

    amount = int(context.args[1])

    cursor.execute("SELECT id FROM users WHERE id=?", (uid,))
    if not cursor.fetchone():
        await update.message.reply_text("❌ Ese usuario no está registrado")
        return

    cursor.execute("UPDATE users SET credits = credits + ? WHERE id=?", (amount, uid))
    db.commit()

    cursor.execute("SELECT name, username, credits FROM users WHERE id=?", (uid,))
    user = cursor.fetchone()

    await update.message.reply_text(f"""
✅ Créditos agregados

🆔 ID: {uid}
➕ Agregado: {amount}
💰 Total: {user[2]}
""")

    try:
        await context.bot.send_message(
            LOG_GROUP_ID,
            f"""
💰 CRÉDITOS AGREGADOS

👤 Nombre: {user[0]}
🆔 ID: {uid}
📛 Usuario: @{user[1]}

➕ Créditos agregados: {amount}
💳 Total actual: {user[2]}
👮 Admin: {update.effective_user.id}
"""
        )
    except Exception as e:
        print("Error log credit:", e)

# ================= DEL CREDIT =================
async def delcred(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ No tienes permiso.\nUsa /cmds")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Uso correcto:\n/delcred ID CANTIDAD")
        return

    uid = context.args[0]

    if not context.args[1].isdigit():
        await update.message.reply_text("❌ La cantidad debe ser un número")
        return

    amount = int(context.args[1])

    cursor.execute("SELECT credits FROM users WHERE id=?", (uid,))
    row = cursor.fetchone()

    if not row:
        await update.message.reply_text("❌ Ese usuario no está registrado")
        return

    old_credits = row[0]
    new_credits = max(old_credits - amount, 0)

    cursor.execute("UPDATE users SET credits=? WHERE id=?", (new_credits, uid))
    db.commit()

    await update.message.reply_text(f"""
✅ Créditos actualizados

🆔 ID: {uid}
Antes: {old_credits}
Ahora: {new_credits}
""")

# ================= COMPRAR =================
async def comprar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)

    cursor.execute("SELECT credits FROM users WHERE id=?", (uid,))
    user = cursor.fetchone()

    if not user:
        await update.message.reply_text("⚠️ Usa /register primero")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Uso correcto:\n/comprar 1")
        return

    cantidad = int(context.args[0])

    if cantidad <= 0:
        await update.message.reply_text("❌ La cantidad debe ser mayor a 0")
        return

    credits = user[0]

    if credits < cantidad:
        kb = [[InlineKeyboardButton("💬 Contactar para recargar", url=f"https://t.me/{OWNER_USERNAME.replace('@', '')}")]]
        await update.message.reply_text(
            "❌ No tienes créditos suficientes.\nUsa /buy para ver precios.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    cursor.execute("SELECT id, item FROM stock LIMIT ?", (cantidad,))
    items = cursor.fetchall()

    if len(items) < cantidad:
        await update.message.reply_text("❌ No hay stock suficiente")
        return

    ids = [int(i[0]) for i in items]
    data = [i[1] for i in items]

    try:
        db.execute("BEGIN")
        placeholders = ",".join(["?"] * len(ids))
        cursor.execute(f"DELETE FROM stock WHERE id IN ({placeholders})", ids)
        cursor.execute("UPDATE users SET credits = credits - ? WHERE id=?", (cantidad, uid))

        compra_id = gen_id()
        items_str = "\n".join(data)
        cursor.execute("INSERT INTO history (user_id, cantidad, items, compra_id) VALUES (?, ?, ?, ?)", (uid, cantidad, items_str, compra_id))

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error en transacción comprar: {e}")
        await update.message.reply_text("❌ Error procesando la compra. Intenta de nuevo.")
        return

    entrega = "\n".join(data)
    texto_compra = f"""
✅ COMPRA REALIZADA

🧾 ID: {compra_id}
📦 Cantidad: {cantidad}

🎁 Entrega:
{entrega}

💰 Créditos restantes: {credits - cantidad}
"""
    try:
        await update.effective_message.reply_photo(photo=open("imagen/Generando.jpeg", "rb"), caption=texto_compra)
    except FileNotFoundError:
        await update.effective_message.reply_text(texto_compra)

# ================= HISTORIA =================
async def historia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)

    cursor.execute("SELECT compra_id, cantidad, items, fecha, id FROM history WHERE user_id=? ORDER BY id DESC", (uid,))
    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("⚠️ No has realizado ninguna compra aún.")
        return

    texto_historia = f"📜 HISTORIAL COMPLETO DE COMPRAS ({len(rows)})\n"

    for idx, row in enumerate(rows, 1):
        compra_id, cantidad, items, fecha, db_id = row
        show_id = compra_id if compra_id else f"#{db_id}"
        texto_historia += f"\n🔹 Compra ID: {show_id} | 📅 {fecha}\n📦 Cantidad: {cantidad} items\n🎁 Ítems:\n{items}\n"

    if len(texto_historia) <= 1024:
        try:
            await update.effective_message.reply_photo(photo=open("imagen/Estadisticas.jpeg", "rb"), caption=texto_historia)
        except FileNotFoundError:
            await update.effective_message.reply_text(texto_historia)
    else:
        for i in range(0, len(texto_historia), 4000):
            await update.effective_message.reply_text(texto_historia[i:i+4000])

# ================= COMPRAS ADMIN =================
async def compras(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ No tienes permiso.\nUsa /cmds")
        return

    if not context.args:
        await update.message.reply_text("Uso correcto:\n/compras @usuario\n/compras ID")
        return

    user = buscar_usuario_por_arg(context.args[0])

    if not user:
        await update.message.reply_text("❌ Usuario no registrado.")
        return

    uid, name, username, credits = user

    cursor.execute("""
        SELECT compra_id, cantidad, items, fecha, id
        FROM history
        WHERE user_id=?
        ORDER BY id DESC
    """, (uid,))
    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text(f"⚠️ @{username} no tiene compras.")
        return

    texto = f"""
🧾 HISTORIAL DE COMPRAS

👤 Nombre: {name}
📛 Usuario: @{username}
🆔 ID: {uid}
💰 Créditos actuales: {credits}
📦 Total compras: {len(rows)}
"""

    for row in rows:
        compra_id, cantidad, items, fecha, db_id = row
        show_id = compra_id if compra_id else f"#{db_id}"
        texto += f"""

━━━━━━━━━━━━━━
🧾 Compra ID: {show_id}
📅 Fecha: {fecha}
📦 Cantidad: {cantidad}

🎁 Items:
{items}
"""

    for i in range(0, len(texto), 4000):
        await update.message.reply_text(texto[i:i+4000])

# ================= INFO ADMIN =================
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ No tienes permiso.\nUsa /cmds")
        return

    target = None

    if update.message.reply_to_message:
        target = str(update.message.reply_to_message.from_user.id)
    elif context.args:
        target = context.args[0]
    else:
        await update.message.reply_text("Uso correcto:\n/info ID\n/info @usuario\nO responde a un mensaje con /info")
        return

    user = buscar_usuario_por_arg(target)

    if not user:
        await update.message.reply_text("❌ Usuario no registrado.")
        return

    uid, name, username, credits = user

    cursor.execute("SELECT COUNT(*) FROM history WHERE user_id=?", (uid,))
    total_compras = cursor.fetchone()[0]

    await update.message.reply_text(f"""
👤 INFO USUARIO

👤 Nombre: {name}
📛 Usuario: @{username}
🆔 ID: {uid}
💰 Créditos: {credits}
🧾 Compras realizadas: {total_compras}
""")

# ================= ANUNCIO =================
async def anuncio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ No tienes permiso.\nUsa /cmds")
        return

    keyboard = [[InlineKeyboardButton("Únete al Grupo", url=CHANNEL)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    cursor.execute("SELECT id FROM users")
    users = cursor.fetchall()

    enviados = 0
    fallidos = 0

    if update.message.reply_to_message:
        for u in users:
            try:
                await context.bot.copy_message(
                    chat_id=u[0],
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.reply_to_message.message_id,
                    reply_markup=reply_markup
                )
                enviados += 1
            except:
                fallidos += 1
    else:
        mensaje = " ".join(context.args) if context.args else ""
        photo_id = update.message.photo[-1].file_id if update.message.photo else None

        if update.message.photo and update.message.caption:
            mensaje = update.message.caption.replace('/anuncio', '').strip()

        if not mensaje and not photo_id:
            await update.message.reply_text("💡 Para anuncios con formato o emojis premium: Responde a un mensaje tuyo con /anuncio\n\nO directamente:\n/anuncio TEXTO")
            return

        text_to_send = f"📢 ANUNCIO\n\n{mensaje}" if mensaje else "📢 ANUNCIO"

        for u in users:
            try:
                if photo_id:
                    await context.bot.send_photo(
                        chat_id=u[0],
                        photo=photo_id,
                        caption=text_to_send,
                        reply_markup=reply_markup
                    )
                else:
                    await context.bot.send_message(
                        chat_id=u[0],
                        text=text_to_send,
                        reply_markup=reply_markup
                    )
                enviados += 1
            except:
                fallidos += 1

    await update.message.reply_text(f"""
📢 Anuncio enviado

✅ Enviados: {enviados}
❌ Fallidos: {fallidos}
""")

# ================= UNKNOWN =================
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Comando incorrecto.\nUsa /cmds")

# ================= MAIN =================
def main():
    if not TOKEN or TOKEN == "PON_AQUI_TU_TOKEN":
        print("❌ Configura TELEGRAM_BOT_TOKEN en el archivo .env")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cmds", cmds))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("me", me))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("stock", stock))
    app.add_handler(CommandHandler("resetstock", resetstock))
    app.add_handler(CommandHandler("addcred", addcred))
    app.add_handler(CommandHandler("delcred", delcred))
    app.add_handler(CommandHandler("comprar", comprar))
    app.add_handler(CommandHandler("historia", historia))
    app.add_handler(CommandHandler("compras", compras))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("anuncio", anuncio))

    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    app.add_error_handler(error_handler)

    print("BOT LISTO")
    
    import asyncio
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    app.run_polling()

if __name__ == "__main__":
    main()