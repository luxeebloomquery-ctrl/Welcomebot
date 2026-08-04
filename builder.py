from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database as db
from utils.admin import is_admin
from utils.buttons import extract_buttons, buttons_to_json, buttons_from_json, build_keyboard
from utils.placeholders import apply_placeholders

router = Router()


class BuilderStates(StatesGroup):
    waiting_text = State()


def _builder_menu(settings: dict) -> InlineKeyboardMarkup:
    status_label = "🟢 ON — tap to turn OFF" if settings["enabled"] else "🔴 OFF — tap to turn ON"
    card_label = "🖼 Card: ON" if settings.get("welcome_card") else "🖼 Card: OFF"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=status_label, callback_data="builder:toggle")],
            [InlineKeyboardButton(text="✏️ Edit Text", callback_data="builder:edittext")],
            [InlineKeyboardButton(text=card_label, callback_data="builder:togglecard")],
            [InlineKeyboardButton(text="👁 Preview", callback_data="builder:preview")],
            [InlineKeyboardButton(text="✅ Done", callback_data="builder:close")],
        ]
    )


@router.message(Command("builder"))
async def cmd_builder(message: Message, bot: Bot):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.")
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.")
        return

    await db.ensure_chat_row(message.chat.id, message.chat.title or "")
    settings = await db.get_settings(message.chat.id)
    await message.answer(
        "<b>🛠 Welcome Builder</b>\nNeeche buttons se apna welcome message customize karo:",
        reply_markup=_builder_menu(settings),
    )


@router.callback_query(F.data == "builder:toggle")
async def builder_toggle(callback: CallbackQuery, bot: Bot):
    if not await is_admin(bot, callback.message.chat, callback.from_user):
        await callback.answer("Sirf admins use kar sakte hain.", show_alert=True)
        return

    settings = await db.get_settings(callback.message.chat.id)
    await db.set_enabled(callback.message.chat.id, not settings["enabled"])
    new_settings = await db.get_settings(callback.message.chat.id)
    await callback.message.edit_reply_markup(reply_markup=_builder_menu(new_settings))
    await callback.answer("Updated!")


@router.callback_query(F.data == "builder:togglecard")
async def builder_togglecard(callback: CallbackQuery, bot: Bot):
    if not await is_admin(bot, callback.message.chat, callback.from_user):
        await callback.answer("Sirf admins use kar sakte hain.", show_alert=True)
        return

    settings = await db.get_settings(callback.message.chat.id)
    await db.set_welcome_card(callback.message.chat.id, not settings.get("welcome_card"))
    new_settings = await db.get_settings(callback.message.chat.id)
    await callback.message.edit_reply_markup(reply_markup=_builder_menu(new_settings))
    await callback.answer("Updated!")


@router.callback_query(F.data == "builder:edittext")
async def builder_edittext(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not await is_admin(bot, callback.message.chat, callback.from_user):
        await callback.answer("Sirf admins use kar sakte hain.", show_alert=True)
        return

    await state.set_state(BuilderStates.waiting_text)
    await state.update_data(chat_id=callback.message.chat.id, admin_id=callback.from_user.id)
    await callback.message.answer(
        "✏️ Naya welcome text bhejo (placeholders: {first} {mention} {chatname} {count}, "
        "buttons: <code>[Text](buttonurl:https://link.com)</code>)"
    )
    await callback.answer()


@router.message(StateFilter(BuilderStates.waiting_text))
async def builder_receive_text(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    if message.from_user.id != data.get("admin_id"):
        return

    chat_id = data.get("chat_id")
    clean_text, button_rows = extract_buttons(message.text or "")
    buttons_json = buttons_to_json(button_rows)
    await db.set_welcome_text(chat_id, clean_text or db.DEFAULT_TEXT, buttons_json)
    await state.clear()

    settings = await db.get_settings(chat_id)
    await message.answer(
        "✅ Text update ho gaya!", reply_markup=_builder_menu(settings)
    )


@router.callback_query(F.data == "builder:preview")
async def builder_preview(callback: CallbackQuery, bot: Bot):
    chat = callback.message.chat
    settings = await db.get_settings(chat.id)
    member_count = await db.get_member_count_placeholder(bot, chat.id)
    text = apply_placeholders(settings["text"], callback.from_user, chat, member_count)
    keyboard = build_keyboard(buttons_from_json(settings["buttons"]))
    await bot.send_message(chat.id, text, reply_markup=keyboard)
    await callback.answer("Preview bhej diya!")


@router.callback_query(F.data == "builder:close")
async def builder_close(callback: CallbackQuery):
    await callback.message.edit_text("✅ Welcome Builder band ho gaya. /builder se dobara khol sakte ho.")
    await callback.answer()
