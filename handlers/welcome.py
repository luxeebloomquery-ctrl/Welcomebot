@router.message(Command("setwelcome"))
@router.message(F.caption.contains("/setwelcome"))
async def cmd_setwelcome(message: Message, command: CommandObject = None, bot: Bot = None):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.", link_preview_options=get_link_preview_config())
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.", link_preview_options=get_link_preview_config())
        return

    await db.ensure_chat_row(message.chat.id, message.chat.title or "")

    reply = message.reply_to_message
    media_type, file_id = None, None
    raw_text = command.args if (command and command.args) else ""

    if message.photo:
        media_type, file_id = "photo", message.photo[-1].file_id
    elif message.video:
        media_type, file_id = "video", message.video.file_id
    elif message.animation:
        media_type, file_id = "animation", message.animation.file_id
    elif message.document:
        media_type, file_id = "document", message.document.file_id

    if message.caption and not raw_text:
        caption_text = message.caption
        if "/setwelcome" in caption_text:
            raw_text = caption_text.split("/setwelcome", 1)[1].strip()
        else:
            raw_text = caption_text.strip()

    if not file_id and reply:
        media_type, file_id = _media_type_and_id(reply)
        if reply.caption and not raw_text:
            raw_text = reply.caption
        elif reply.text and not raw_text:
            raw_text = reply.text

    if not raw_text and not file_id:
        await message.answer(
            "Kuch text do ya media pe reply karke caption ke sath likho.\n"
            "Example: <code>/setwelcome Welcome {mention} to {chatname}!</code>",
            parse_mode="HTML",
            link_preview_options=get_link_preview_config(),
        )
        return

    clean_text, button_rows = extract_buttons(raw_text)
    buttons_json = buttons_to_json(button_rows)

    if not clean_text:
        clean_text = db.DEFAULT_TEXT if not file_id else ""

    if file_id:
        await db.set_welcome_card(message.chat.id, False)

    if file_id and media_type:
        # Video heavy processing bypass -> direct instant save
        await db.set_welcome_media(message.chat.id, clean_text, buttons_json, file_id, media_type)
    else:
        await db.set_welcome_text(message.chat.id, clean_text, buttons_json)

    await message.answer("✅ Welcome message set ho gaya! Check karne ke liye /preview use karo.", link_preview_options=get_link_preview_config())
    
