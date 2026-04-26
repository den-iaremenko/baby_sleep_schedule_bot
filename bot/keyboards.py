from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📅 Schedule"), KeyboardButton("⚙️ Setup")],
        [KeyboardButton("😴 Slept"),    KeyboardButton("🌅 Woke up")],
    ],
    resize_keyboard=True,
)


def build_sleep_keyboard(from_nap: int, total_naps: int) -> InlineKeyboardMarkup:
    """Inline keyboard with start/end buttons for naps from_nap..total_naps plus night sleep."""
    rows = [
        [
            InlineKeyboardButton(f"😴 Nap {i} start", callback_data=f"sleep_start:nap_{i}"),
            InlineKeyboardButton(f"🌅 Nap {i} end",   callback_data=f"sleep_end:nap_{i}"),
        ]
        for i in range(from_nap, total_naps + 1)
    ]
    rows.append([
        InlineKeyboardButton("🌙 Night sleep start", callback_data="sleep_start:night"),
        InlineKeyboardButton("🌅 Night sleep end",   callback_data="sleep_end:night"),
    ])
    return InlineKeyboardMarkup(rows)
