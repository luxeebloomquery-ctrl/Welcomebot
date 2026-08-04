@router.message(Command("setwelcome"))
@router.message(F.caption.startswith("/setwelcome"))
async def cmd_setwelcome(message: Message, command: CommandObject = None, bot: Bot = None):
    if message.chat.type == "private":
        await message.answer("Ye command sirf groups mein kaam karta hai.", link_preview_options=NO_LINK_PREVIEW)
        return
    if not await is_admin(bot, message.chat, message.from_user):
        await message.answer("Ye command sirf group admins use kar sakte hain.", link_preview_options=NO_LINK_PREVIEW)
        return

    await db.ensure_chat_row(message.chat.id, message.chat.title or "")

    reply = message.reply_to_message
    media_type, file_id = None, None
    raw_text = command.args if (command and command.args) else ""

    # Agar direct video/photo/animation/doc ke sath /setwelcome caption me hai
    if message.photo:
        media_type, file_id = "photo", message.photo[-1].file_id
    elif message.video:
        media_type, file_id = "video", message.video.file_id
    elif message.animation:
        media_type, file_id = "animation", message.animation.file_id
    elif message.document:
        media_type, file_id = "document", message.document.file_id

    # Caption me se command hatayein
    if file_id and message.caption and not raw_text:
        raw_text = message.caption.replace("/setwelcome", "").strip()

    # Agar purani media message par reply karke command di ho
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
            link_preview_options=NO_LINK_PREVIEW,
        )
        return

    clean_text, button_rows = extract_buttons(raw_text)
    buttons_json = buttons_to_json(button_rows)

    if not clean_text:
        clean_text = db.DEFAULT_TEXT if not file_id else ""

    if file_id:
        await db.set_welcome_card(message.chat.id, False)

    if file_id and media_type:
        if media_type == "video":
            progress = ProgressMessage(bot, message.chat.id)
            await progress.start("🎬 Video process ho raha hai...")
            file_id = await process_video(bot, message.chat.id, file_id, progress)
        await db.set_welcome_media(message.chat.id, clean_text, buttons_json, file_id, media_type)
    else:
        await db.set_welcome_text(message.chat.id, clean_text, buttons_json)

    await message.answer("✅ Welcome message set ho gaya! Check karne ke liye /preview use karo.", link_preview_options=NO_LINK_PREVIEW)
    
