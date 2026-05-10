from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import filters

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📅 Розклад"), KeyboardButton("☀️ Ранковий підйом")],
        [KeyboardButton("😴 Спить"), KeyboardButton("🌅 Прокинувся")],
        [KeyboardButton("⚙️ Налаштування")],
    ],
    resize_keyboard=True,
)

SLEEP_ACTIONS_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("😴 Спить", callback_data="sleep:start"),
    InlineKeyboardButton("🌅 Прокинувся", callback_data="sleep:end"),
]])

# Matches every reply-keyboard button — used by conversation handlers as a fallback
# filter so that pressing a menu button never gets swallowed by an open conversation.
BUTTON_FILTER = filters.Regex(
    r"^(📅 Розклад|⚙️ Налаштування|☀️ Ранковий підйом|😴 Спить|🌅 Прокинувся)$"
)
