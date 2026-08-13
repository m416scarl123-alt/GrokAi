import base64
import io
import secrets
import string

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

import db
from config import settings
from xai_client import XAI

xai = XAI(
    settings.xai_api_key,
    settings.xai_model,
    settings.xai_image_model,
    settings.xai_voice_id,
)

def gen_code():
    alphabet = string.ascii_uppercase + string.digits
    parts = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3)]
    return "GROK-" + "-".join(parts)

async def ensure_user(update):
    await db.upsert_user(update.effective_user)
    return await db.get_user(update.effective_user.id)

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🆕 Новый чат", callback_data="newchat")],
        [InlineKeyboardButton("🧹 Очистить память", callback_data="clear")],
    ])

async def start(update, context):
    u = await ensure_user(update)
    if u["blocked"]:
        await update.message.reply_text("🚫 Твой доступ заблокирован.")
        return
    if not u["activated"]:
        context.user_data["awaiting_activation"] = True
        await update.message.reply_text(
            "🤖 Привет! Это Grok AI.\n\n🔐 Для доступа введи код активации."
        )
        return
    await update.message.reply_text(
        "🤖 Grok AI готов. Просто напиши сообщение.",
        reply_markup=main_keyboard(),
    )

async def clear_cmd(update, context):
    u = await ensure_user(update)
    if not u["activated"] or u["blocked"]:
        return
    await db.clear_history(update.effective_user.id)
    await update.message.reply_text("🧹 Память очищена.")

async def image_cmd(update, context):
    u = await ensure_user(update)
    if not u["activated"] or u["blocked"]:
        return
    if not u["full_access"]:
        await update.message.reply_text(
            "🔒 Генерация изображений доступна после полного доступа."
        )
        return
    prompt = " ".join(context.args).strip()
    if not prompt:
        await update.message.reply_text(
            "Использование: /image космонавт на Марсе, кинематографично"
        )
        return
    await update.message.reply_text("🎨 Генерирую...")
    try:
        result = await xai.generate_image(prompt)
        if result.startswith("http"):
            await update.message.reply_photo(result, caption="🎨 Готово")
        else:
            await update.message.reply_photo(
                io.BytesIO(base64.b64decode(result)),
                caption="🎨 Готово",
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка генерации: {e}")

async def voice_cmd(update, context):
    u = await ensure_user(update)
    if not u["activated"] or u["blocked"]:
        return
    mode = context.args[0].lower() if context.args else ""
    if mode not in {"on", "off"}:
        await update.message.reply_text("Использование: /voice on или /voice off")
        return
    if mode == "on" and not u["full_access"]:
        await update.message.reply_text("🔒 Голосовые ответы доступны после /nonstop.")
        return
    context.user_data["voice_reply"] = mode == "on"
    await update.message.reply_text(
        "🔊 Голосовые ответы " + ("включены." if mode == "on" else "выключены.")
    )


async def admin_cmd(update, context):
    if update.effective_user.id != settings.admin_telegram_id:
        await update.message.reply_text("⛔ Нет доступа.")
        return
    context.user_data["admin_pending"] = True
    context.user_data["admin_ok"] = False
    await update.message.reply_text("🔐 Введи пароль администратора.")

async def admin_panel(update, context):
    s = await db.stats()
    keyboard = [
        [InlineKeyboardButton("🔑 Создать ключ", callback_data="admin_create_key")],
        [InlineKeyboardButton("📋 Коды", callback_data="admin_codes")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
    ]
    await update.message.reply_text(
        f"👑 Админ-панель\n\n"
        f"👥 Пользователей: {s['users']}\n"
        f"🔑 Активированных: {s['activated']}\n"
        f"🚀 Полный доступ: {s['full_access']}\n"
        f"🚫 Заблокировано: {s['blocked']}\n"
        f"💬 Запросов: {s['requests']}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def nonstop(update, context):
    if update.effective_user.id != settings.admin_telegram_id:
        await update.message.reply_text("⛔ Нет доступа.")
        return
    if not context.user_data.get("admin_ok"):
        await update.message.reply_text("🔐 Сначала /admin и код из Gmail.")
        return
    target = " ".join(context.args).strip()
    if not target:
        await update.message.reply_text("Использование: /nonstop @username")
        return
    username = target.lstrip("@")
    async with db.POOL.acquire() as c:
        row = await c.fetchrow(
            "SELECT telegram_id FROM users WHERE lower(username)=lower($1)",
            username,
        )
    if not row:
        await update.message.reply_text("Пользователь не найден в базе.")
        return
    await db.set_full_access(row["telegram_id"], True)
    await update.message.reply_text(f"🚀 Полный доступ включён для @{username}.")

async def callback(update, context):
    q = update.callback_query
    await q.answer()
    if q.data == "newchat":
        await db.clear_history(q.from_user.id)
        await q.message.reply_text("🆕 Новый чат создан.")
    elif q.data == "clear":
        await db.clear_history(q.from_user.id)
        await q.message.reply_text("🧹 Память очищена.")
    elif q.data == "admin_create_key":
        if q.from_user.id != settings.admin_telegram_id or not context.user_data.get("admin_ok"):
            return
        code = gen_code()
        await db.create_activation_code(code, settings.activation_code_uses)
        await q.message.reply_text(
            f"🔑 Новый код:\n`{code}`\n\n"
            f"Использований: 0/{settings.activation_code_uses}\nСрок: ♾️",
            parse_mode="Markdown",
        )
    elif q.data == "admin_codes":
        if q.from_user.id != settings.admin_telegram_id or not context.user_data.get("admin_ok"):
            return
        rows = await db.list_codes()
        if not rows:
            await q.message.reply_text("Кодов пока нет.")
            return
        text = "\n".join(
            f"`{r['code']}` — {r['uses']}/{r['max_uses']} "
            f"{'🚫' if r['revoked'] else '🟢'}"
            for r in rows
        )
        await q.message.reply_text(text, parse_mode="Markdown")
    elif q.data == "admin_stats":
        if q.from_user.id != settings.admin_telegram_id or not context.user_data.get("admin_ok"):
            return
        s = await db.stats()
        await q.message.reply_text(
            f"📊 Статистика\n\n"
            f"Пользователи: {s['users']}\n"
            f"Активации: {s['activated']}\n"
            f"Полный доступ: {s['full_access']}\n"
            f"Блокировки: {s['blocked']}\n"
            f"Запросы: {s['requests']}"
        )

async def process_text(update, context, text, image_bytes=None):
    u = await db.get_user(update.effective_user.id)
    if not u or not u["activated"] or u["blocked"]:
        await update.message.reply_text("🔐 Сначала активируй доступ.")
        return

    history = await db.get_history(update.effective_user.id, settings.memory_messages)
    await db.add_message(
        update.effective_user.id,
        "user",
        text if not image_bytes else "[изображение] " + text,
        settings.memory_messages,
    )
    history.append({"role": "user", "content": text})
    await update.message.chat.send_action("typing")

    try:
        answer = await xai.chat(
            history,
            use_web=bool(u["full_access"]),
            image_bytes=image_bytes,
            image_mime="image/jpeg",
        )
        await db.add_message(
            update.effective_user.id,
            "assistant",
            answer,
            settings.memory_messages,
        )
        await db.increment_requests(update.effective_user.id)
        await update.message.reply_text(answer)

        if context.user_data.get("voice_reply") and u["full_access"]:
            audio = await xai.tts(answer, "auto")
            await update.message.reply_voice(
                io.BytesIO(audio), filename="grok.mp3"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка Grok API: {e}")

async def text_message(update, context):
    u = await ensure_user(update)
    text = update.message.text or ""

    if (
        context.user_data.get("admin_pending")
        and update.effective_user.id == settings.admin_telegram_id
    ):
        if secrets.compare_digest(text.strip(), settings.admin_password):
            context.user_data["admin_pending"] = False
            context.user_data["admin_ok"] = True
            await admin_panel(update, context)
        else:
            await update.message.reply_text("❌ Неверный пароль.")
        return

    if not u["activated"]:
        ok, reason = await db.activate_code(text.strip(), update.effective_user.id)
        if ok:
            context.user_data["awaiting_activation"] = False
            await update.message.reply_text("✅ Доступ активирован навсегда!")
        elif reason == "already":
            await update.message.reply_text("ℹ️ Этот код уже использован тобой.")
        else:
            await update.message.reply_text("❌ Неверный или исчерпанный код.")
        return

    await process_text(update, context, text)

async def photo(update, context):
    u = await ensure_user(update)
    if not u["activated"] or u["blocked"]:
        await update.message.reply_text("🔐 Сначала активируй доступ.")
        return
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    buf = io.BytesIO()
    await tg_file.download_to_memory(buf)
    caption = update.message.caption or "Что на изображении? Проанализируй подробно."
    await process_text(update, context, caption, image_bytes=buf.getvalue())

async def voice(update, context):
    u = await ensure_user(update)
    if not u["activated"] or u["blocked"]:
        await update.message.reply_text("🔐 Сначала активируй доступ.")
        return
    tg_file = await context.bot.get_file(update.message.voice.file_id)
    buf = io.BytesIO()
    await tg_file.download_to_memory(buf)
    try:
        text = await xai.stt(buf.getvalue(), "voice.ogg")
        await update.message.reply_text(f"🎤 Я услышал:\n{text}")
        await process_text(update, context, text)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка распознавания голоса: {e}")

async def post_init(app):
    await db.init_db(settings.database_url)

def main():
    if not settings.external_url:
        raise RuntimeError("RENDER_EXTERNAL_URL is missing.")
    if not settings.webhook_secret:
        raise RuntimeError("WEBHOOK_SECRET is missing.")

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(CommandHandler("newchat", clear_cmd))
    app.add_handler(CommandHandler("image", image_cmd))
    app.add_handler(CommandHandler("voice", voice_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("nonstop", nonstop))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.PHOTO, photo))
    app.add_handler(MessageHandler(filters.VOICE, voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))

    webhook_path = f"telegram/{settings.webhook_secret}"
    app.run_webhook(
        listen="0.0.0.0",
        port=settings.port,
        url_path=webhook_path,
        webhook_url=f"{settings.external_url}/{webhook_path}",
        secret_token=settings.webhook_secret,
        allowed_updates=Update.ALL_TYPES,
    )

if __name__ == "__main__":
    main()
