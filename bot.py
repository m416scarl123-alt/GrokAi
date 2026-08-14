import base64
import io
import secrets
import string

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import db
from config import settings
from xai_client import XAI


# =========================================================
# НАСТРОЙКИ
# =========================================================

OWNER_ID = 8237924471

xai = XAI(
    settings.xai_api_key,
    settings.xai_model,
    settings.xai_image_model,
    settings.xai_voice_id,
)


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def gen_code():
    alphabet = string.ascii_uppercase + string.digits

    parts = [
        "".join(
            secrets.choice(alphabet)
            for _ in range(4)
        )
        for _ in range(3)
    ]

    return "GROK-" + "-".join(parts)


async def ensure_user(update):
    await db.upsert_user(
        update.effective_user
    )

    return await db.get_user(
        update.effective_user.id
    )


def main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🆕 Новый чат",
                callback_data="newchat"
            )
        ],
        [
            InlineKeyboardButton(
                "🧹 Очистить память",
                callback_data="clear"
            )
        ],
    ])


# =========================================================
# START
# =========================================================

async def start(update, context):

    u = await ensure_user(update)

    if u["blocked"]:
        await update.message.reply_text(
            "🚫 Твой доступ заблокирован."
        )
        return

    if not u["activated"]:

        context.user_data[
            "awaiting_activation"
        ] = True

        await update.message.reply_text(
            "🤖 Привет! Это Grok AI.\n\n"
            "🔐 Для доступа введи код активации."
        )

        return

    await update.message.reply_text(
        "🤖 Grok AI готов.\n\n"
        "Просто напиши сообщение.",
        reply_markup=main_keyboard(),
    )


# =========================================================
# ОЧИСТКА ПАМЯТИ
# =========================================================

async def clear_cmd(update, context):

    u = await ensure_user(update)

    if not u["activated"] or u["blocked"]:
        return

    await db.clear_history(
        update.effective_user.id
    )

    await update.message.reply_text(
        "🧹 Память очищена."
    )


# =========================================================
# ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ
# =========================================================

async def image_cmd(update, context):

    u = await ensure_user(update)

    if not u["activated"]:
        await update.message.reply_text(
            "🔐 Сначала активируй доступ."
        )
        return

    if u["blocked"]:
        await update.message.reply_text(
            "🚫 Твой доступ заблокирован."
        )
        return

    if not u["full_access"]:
        await update.message.reply_text(
            "🔒 Генерация изображений доступна "
            "после получения полного доступа."
        )
        return

    prompt = " ".join(
        context.args
    ).strip()

    if not prompt:

        await update.message.reply_text(
            "Использование:\n\n"
            "/image космонавт на Марсе, "
            "кинематографично"
        )

        return

    await update.message.reply_text(
        "🎨 Генерирую..."
    )

    try:

        result = await xai.generate_image(
            prompt
        )

        if result.startswith("http"):

            await update.message.reply_photo(
                result,
                caption="🎨 Готово"
            )

        else:

            image_data = base64.b64decode(
                result
            )

            await update.message.reply_photo(
                io.BytesIO(image_data),
                caption="🎨 Готово"
            )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Ошибка генерации:\n{e}"
        )


# =========================================================
# ГОЛОСОВЫЕ ОТВЕТЫ
# =========================================================

async def voice_cmd(update, context):

    u = await ensure_user(update)

    if not u["activated"] or u["blocked"]:
        return

    mode = (
        context.args[0].lower()
        if context.args
        else ""
    )

    if mode not in {"on", "off"}:

        await update.message.reply_text(
            "Использование:\n\n"
            "/voice on\n"
            "/voice off"
        )

        return

    if mode == "on" and not u["full_access"]:

        await update.message.reply_text(
            "🔒 Голосовые ответы доступны "
            "после получения полного доступа."
        )

        return

    context.user_data[
        "voice_reply"
    ] = mode == "on"

    await update.message.reply_text(
        "🔊 Голосовые ответы "
        + (
            "включены."
            if mode == "on"
            else "выключены."
        )
    )


# =========================================================
# ADMIN
# =========================================================

async def admin_cmd(update, context):

    if (
        update.effective_user.id
        != settings.admin_telegram_id
    ):

        await update.message.reply_text(
            "⛔ Нет доступа."
        )

        return

    context.user_data[
        "admin_pending"
    ] = True

    context.user_data[
        "admin_ok"
    ] = False

    await update.message.reply_text(
        "🔐 Введи пароль администратора."
    )


async def admin_panel(update, context):

    s = await db.stats()

    keyboard = [

        [
            InlineKeyboardButton(
                "🔑 Создать ключ",
                callback_data="admin_create_key"
            )
        ],

        [
            InlineKeyboardButton(
                "📋 Коды",
                callback_data="admin_codes"
            )
        ],

        [
            InlineKeyboardButton(
                "🚫 Бан / разблокировка",
                callback_data="admin_ban_help"
            )
        ],

        [
            InlineKeyboardButton(
                "📊 Статистика",
                callback_data="admin_stats"
            )
        ],

    ]

    await update.message.reply_text(

        f"👑 Админ-панель\n\n"

        f"👥 Пользователей: {s['users']}\n"
        f"🔑 Активированных: {s['activated']}\n"
        f"🚀 Полный доступ: {s['full_access']}\n"
        f"🚫 Заблокировано: {s['blocked']}\n"
        f"💬 Запросов: {s['requests']}",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


# =========================================================
# NONSTOP
# =========================================================

async def nonstop(update, context):

    user_id = update.effective_user.id

    # Только владелец или администратор
    if user_id not in (
        settings.admin_telegram_id,
        OWNER_ID,
    ):

        await update.message.reply_text(
            "⛔ Нет доступа."
        )

        return

    # Владелец может использовать напрямую.
    # Администратору требуется авторизация.
    if (
        user_id != OWNER_ID
        and not context.user_data.get(
            "admin_ok"
        )
    ):

        await update.message.reply_text(
            "🔐 Сначала /admin "
            "и введи пароль администратора."
        )

        return

    target = " ".join(
        context.args
    ).strip()

    if not target:

        await update.message.reply_text(
            "Использование:\n\n"
            "/nonstop @username\n\n"
            "или\n\n"
            "/nonstop telegram_id"
        )

        return

    target = target.lstrip("@")

    async with db.POOL.acquire() as c:

        if target.isdigit():

            row = await c.fetchrow(
                """
                SELECT telegram_id, username
                FROM users
                WHERE telegram_id=$1
                """,
                int(target),
            )

        else:

            row = await c.fetchrow(
                """
                SELECT telegram_id, username
                FROM users
                WHERE lower(username)=lower($1)
                """,
                target,
            )

    if not row:

        await update.message.reply_text(
            "❌ Пользователь не найден в базе.\n\n"
            "Он должен хотя бы один раз "
            "написать боту."
        )

        return

    # ВКЛЮЧАЕМ ПОЛНЫЙ ДОСТУП
    await db.set_full_access(
        row["telegram_id"],
        True
    )

    name = (
        f"@{row['username']}"
        if row["username"]
        else str(row["telegram_id"])
    )

    await update.message.reply_text(
        f"🚀 Полный доступ включён "
        f"для {name}."
    )


# =========================================================
# BAN / UNBAN
# =========================================================

async def _admin_target(
    update,
    context,
    action,
):

    if (
        update.effective_user.id
        != settings.admin_telegram_id
    ):

        await update.message.reply_text(
            "⛔ Нет доступа."
        )

        return

    if not context.user_data.get(
        "admin_ok"
    ):

        await update.message.reply_text(
            "🔐 Сначала /admin "
            "и введи пароль администратора."
        )

        return

    target = " ".join(
        context.args
    ).strip()

    if not target:

        await update.message.reply_text(
            f"Использование:\n\n"
            f"/{action} @username\n\n"
            f"или\n\n"
            f"/{action} telegram_id"
        )

        return

    target = target.lstrip("@")

    async with db.POOL.acquire() as c:

        if target.isdigit():

            row = await c.fetchrow(
                """
                SELECT
                    telegram_id,
                    username,
                    first_name
                FROM users
                WHERE telegram_id=$1
                """,
                int(target),
            )

        else:

            row = await c.fetchrow(
                """
                SELECT
                    telegram_id,
                    username,
                    first_name
                FROM users
                WHERE lower(username)=lower($1)
                """,
                target,
            )

    if not row:

        await update.message.reply_text(
            "❌ Пользователь не найден в базе."
        )

        return

    # Нельзя заблокировать администратора
    if (
        row["telegram_id"]
        == settings.admin_telegram_id
    ):

        await update.message.reply_text(
            "🛡️ Нельзя заблокировать администратора."
        )

        return

    enabled = action == "ban"

    await db.set_blocked(
        row["telegram_id"],
        enabled
    )

    name = (
        f"@{row['username']}"
        if row["username"]
        else (
            row["first_name"]
            or str(row["telegram_id"])
        )
    )

    if enabled:

        await update.message.reply_text(
            f"🚫 Пользователь {name} "
            f"заблокирован."
        )

        try:

            await context.bot.send_message(
                row["telegram_id"],
                "🚫 Твой доступ к Grok AI "
                "заблокирован администратором."
            )

        except Exception:
            pass

    else:

        await update.message.reply_text(
            f"✅ Пользователь {name} "
            f"разблокирован."
        )

        try:

            await context.bot.send_message(
                row["telegram_id"],
                "✅ Твой доступ к Grok AI "
                "восстановлен."
            )

        except Exception:
            pass


async def ban_cmd(update, context):

    await _admin_target(
        update,
        context,
        "ban"
    )


async def unban_cmd(update, context):

    await _admin_target(
        update,
        context,
        "unban"
    )


# =========================================================
# CALLBACK
# =========================================================

async def callback(update, context):

    q = update.callback_query

    await q.answer()

    # -----------------------------------------------------
    # НОВЫЙ ЧАТ
    # -----------------------------------------------------

    if q.data == "newchat":

        await db.clear_history(
            q.from_user.id
        )

        await q.message.reply_text(
            "🆕 Новый чат создан."
        )

    # -----------------------------------------------------
    # ОЧИСТКА
    # -----------------------------------------------------

    elif q.data == "clear":

        await db.clear_history(
            q.from_user.id
        )

        await q.message.reply_text(
            "🧹 Память очищена."
        )

    # -----------------------------------------------------
    # СОЗДАТЬ КОД
    # -----------------------------------------------------

    elif q.data == "admin_create_key":

        if (
            q.from_user.id
            != settings.admin_telegram_id
            or not context.user_data.get(
                "admin_ok"
            )
        ):

            return

        code = gen_code()

        await db.create_activation_code(
            code,
            settings.activation_code_uses
        )

        await q.message.reply_text(

            f"🔑 Новый код:\n"
            f"`{code}`\n\n"

            f"Использований: "
            f"0/{settings.activation_code_uses}\n"

            f"Срок: ♾️",

            parse_mode="Markdown",
        )

    # -----------------------------------------------------
    # КОДЫ
    # -----------------------------------------------------

    elif q.data == "admin_codes":

        if (
            q.from_user.id
            != settings.admin_telegram_id
            or not context.user_data.get(
                "admin_ok"
            )
        ):

            return

        rows = await db.list_codes()

        if not rows:

            await q.message.reply_text(
                "Кодов пока нет."
            )

            return

        text = "\n".join(

            f"`{r['code']}` — "
            f"{r['uses']}/{r['max_uses']} "
            f"{'🚫' if r['revoked'] else '🟢'}"

            for r in rows
        )

        await q.message.reply_text(
            text,
            parse_mode="Markdown"
        )

    # -----------------------------------------------------
    # BAN HELP
    # -----------------------------------------------------

    elif q.data == "admin_ban_help":

        if (
            q.from_user.id
            != settings.admin_telegram_id
            or not context.user_data.get(
                "admin_ok"
            )
        ):

            return

        await q.message.reply_text(

            "🚫 Управление пользователями\n\n"

            "Заблокировать:\n"
            "`/ban @username`\n\n"

            "или:\n"
            "`/ban telegram_id`\n\n"

            "Разблокировать:\n"
            "`/unban @username`",

            parse_mode="Markdown",
        )

    # -----------------------------------------------------
    # СТАТИСТИКА
    # -----------------------------------------------------

    elif q.data == "admin_stats":

        if (
            q.from_user.id
            != settings.admin_telegram_id
            or not context.user_data.get(
                "admin_ok"
            )
        ):

            return

        s = await db.stats()

        await q.message.reply_text(

            f"📊 Статистика\n\n"

            f"👥 Пользователи: "
            f"{s['users']}\n"

            f"🔑 Активации: "
            f"{s['activated']}\n"

            f"🚀 Полный доступ: "
            f"{s['full_access']}\n"

            f"🚫 Блокировки: "
            f"{s['blocked']}\n"

            f"💬 Запросы: "
            f"{s['requests']}"
        )


# =========================================================
# ОБРАБОТКА ТЕКСТА
# =========================================================

async def process_text(
    update,
    context,
    text,
    image_bytes=None,
):

    u = await db.get_user(
        update.effective_user.id
    )

    if (
        not u
        or not u["activated"]
        or u["blocked"]
    ):

        await update.message.reply_text(
            "🔐 Сначала активируй доступ."
        )

        return

    history = await db.get_history(
        update.effective_user.id,
        settings.memory_messages
    )

    await db.add_message(

        update.effective_user.id,

        "user",

        (
            text
            if not image_bytes
            else "[изображение] " + text
        ),

        settings.memory_messages,
    )

    history.append({
        "role": "user",
        "content": text,
    })

    await update.message.chat.send_action(
        "typing"
    )

    try:

        answer = await xai.chat(

            history,

            use_web=bool(
                u["full_access"]
            ),

            image_bytes=image_bytes,

            image_mime="image/jpeg",
        )

        await db.add_message(

            update.effective_user.id,

            "assistant",

            answer,

            settings.memory_messages,
        )

        await db.increment_requests(
            update.effective_user.id
        )

        await update.message.reply_text(
            answer
        )

        # Голосовой ответ
        if (
            context.user_data.get(
                "voice_reply"
            )
            and u["full_access"]
        ):

            audio = await xai.tts(
                answer,
                "auto"
            )

            await update.message.reply_voice(
                io.BytesIO(audio),
                filename="grok.mp3"
            )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Ошибка Grok API:\n{e}"
        )


# =========================================================
# ТЕКСТОВЫЕ СООБЩЕНИЯ
# =========================================================

async def text_message(
    update,
    context,
):

    u = await ensure_user(update)

    text = (
        update.message.text
        or ""
    )

    # -----------------------------------------------------
    # ПАРОЛЬ АДМИНИСТРАТОРА
    # -----------------------------------------------------

    if (
        context.user_data.get(
            "admin_pending"
        )
        and update.effective_user.id
        == settings.admin_telegram_id
    ):

        if (
            text.strip()
            == settings.admin_password
        ):

            context.user_data[
                "admin_pending"
            ] = False

            context.user_data[
                "admin_ok"
            ] = True

            await admin_panel(
                update,
                context
            )

        else:

            await update.message.reply_text(
                "❌ Неверный пароль."
            )

        return

    # -----------------------------------------------------
    # АК
