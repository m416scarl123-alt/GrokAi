import base64
import io
import os
import secrets
import string

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
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
        "🤖 Grok AI готов. Просто напиши сообщение.",
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

    if not u["full_access"] and not u["image_access"]:

        await update.message.reply_text(
            "🔒 У тебя нет доступа "
            "к генерации изображений."
        )

        return

    prompt = " ".join(
        context.args
    ).strip()

    if not prompt:

        await update.message.reply_text(
            "Использование:\n"
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

            await update.message.reply_photo(
                io.BytesIO(
                    base64.b64decode(result)
                ),
                caption="🎨 Готово"
            )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Ошибка генерации:\n{e}"
        )


# =========================================================
# ВЫДАТЬ ДОСТУП К ИЗОБРАЖЕНИЯМ
# =========================================================

async def imaging(update, context):

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
            "Использование:\n"
            "/imaging @username\n"
            "или\n"
            "/imaging telegram_id"
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
            "❌ Пользователь не найден в базе.\n\n"
            "Он должен хотя бы один раз "
            "написать боту."
        )

        return

    await db.set_image_access(
        row["telegram_id"],
        True
    )

    name = (
        f"@{row['username']}"
        if row["username"]
        else (
            row["first_name"]
            or str(row["telegram_id"])
        )
    )

    await update.message.reply_text(
        f"🖼️ Доступ к генерации "
        f"изображений выдан {name}."
    )

    try:

        await context.bot.send_message(
            row["telegram_id"],
            "🖼️ Тебе выдан доступ "
            "к генерации изображений!\n\n"
            "Используй:\n"
            "/image описание изображения",
        )

    except Exception:

        pass


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
            "Использование:\n"
            "/voice on\n"
            "/voice off"
        )

        return

    if mode == "on" and not u["full_access"]:

        await update.message.reply_text(
            "🔒 Голосовые ответы доступны "
            "после /nonstop."
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

        f"👥 Пользователей: "
        f"{s['users']}\n"

        f"🔑 Активированных: "
        f"{s['activated']}\n"

        f"🚀 Полный доступ: "
        f"{s['full_access']}\n"

        f"🖼️ Доступ к изображениям: "
        f"{s['image_access']}\n"

        f"🚫 Заблокировано: "
        f"{s['blocked']}\n"

        f"💬 Запросов: "
        f"{s['requests']}",

        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


# =========================================================
# NONSTOP
# =========================================================

async def nonstop(update, context):

    user_id = update.effective_user.id

    if user_id not in (
        settings.admin_telegram_id,
        OWNER_ID,
    ):
        await update.message.reply_text(
            "⛔ Нет доступа."
        )
        return
