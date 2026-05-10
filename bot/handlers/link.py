import uuid

from telegram import Update
from telegram.ext import CommandHandler, ConversationHandler, ContextTypes, MessageHandler, filters

from db.engine import AsyncSessionLocal
from db import repository
from keyboards import BUTTON_FILTER, MAIN_KEYBOARD

ASK_BABY_ID = 0



async def cmd_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🔗 Введіть Baby ID для підключення:\n"
        "_(Baby ID можна знайти у /profile)_",
        parse_mode="Markdown",
    )
    return ASK_BABY_ID


async def receive_baby_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    try:
        baby_id = uuid.UUID(text)
    except ValueError:
        await update.message.reply_text(
            "❌ Невірний формат Baby ID. Спробуйте ще раз або /cancel для скасування.",
            reply_markup=MAIN_KEYBOARD,
        )
        return ASK_BABY_ID

    async with AsyncSessionLocal() as db:
        profile = await repository.get_baby_profile_by_id(db, baby_id)

    if not profile:
        await update.message.reply_text(
            "❌ Профіль з таким Baby ID не знайдено.",
            reply_markup=MAIN_KEYBOARD,
        )
        return ConversationHandler.END

    profile_name = profile.name

    async with AsyncSessionLocal() as db:
        status = await repository.link_user_to_baby(db, update.effective_user.id, baby_id)

    if status == "already_linked":
        await update.message.reply_text(
            f"ℹ️ Ви вже підключені до профілю *{profile_name}*.",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )
    else:
        await update.message.reply_text(
            f"✅ Успішно підключено до профілю *{profile_name}*!\n\n"
            "Тепер ви бачите той самий розклад і сни.",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )

    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Скасовано.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END


def link_conv_handler() -> ConversationHandler:
    text_only = filters.TEXT & ~filters.COMMAND & ~_BUTTON_FILTER
    return ConversationHandler(
        entry_points=[CommandHandler("link", cmd_link)],
        states={
            ASK_BABY_ID: [MessageHandler(text_only, receive_baby_id)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )
