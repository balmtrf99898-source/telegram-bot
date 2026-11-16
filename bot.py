import logging
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

# إعداد السجلات لمتابعة عمل البوت
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# توكن البوت الخاص بك
BOT_TOKEN = "9125820336:AAEcAenOPHzbxSxCtGDjRczZ0lZzd57yX04"

# قاموس لتخزين حالة الحماية لكل مجموعة (افتراضياً مفعلة True)
group_protection = {}

# دالة التحقق مما إذا كان المستخدم مشرفاً أو مالكاً في المجموعة
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int = None) -> bool:
    chat = update.effective_chat
    if chat.type == 'private':
        return True
    
    target_id = user_id if user_id else update.effective_user.id
    member = await chat.get_member(target_id)
    return member.status in ['administrator', 'creator']

# --- أوامر التحكم العامة ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر الترحيب وشرح الأوامر"""
    help_text = (
        "مرحباً! أنا بوت حماية وإدارة المجموعات الذكي. 🛡️\n\n"
        "**أوامر المشرفين:**\n"
        "• `/enable` : تفعيل الحماية التلقائية (الروابط والتوجيه)\n"
        "• `/disable` : تعطيل الحماية التلقائية\n"
        "• `/status` : معرفة حالة الحماية الحالية\n\n"
        "**أوامر العقوبات (بالرد على رسالة العضو):**\n"
        "• `/ban` : حظر العضو وطرده نهائياً\n"
        "• `/unban` : إلغاء حظر العضو\n"
        "• `/mute` : كتم العضو (منعه من إرسال الرسائل)\n"
        "• `/unmute` : إلغاء الكتم وإعادة الصلاحيات\n"
        "• `/restrict` : تقييد العضو (منع الوسائط والملصقات والروابط، والسماح بالنص فقط)"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def enable_protection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("عذراً، هذا الأمر للمشرفين فقط! 🚫")
        return
    
    group_protection[update.effective_chat.id] = True
    await update.message.reply_text("✅ تم **تفعيل** نظام الحماية التلقائية في هذه المجموعة.", parse_mode="Markdown")

async def disable_protection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        await update.message.reply_text("عذراً، هذا الأمر للمشرفين فقط! 🚫")
        return
    
    group_protection[update.effective_chat.id] = False
    await update.message.reply_text("⚠️ تم **تعطيل** نظام الحماية التلقائية مؤقتاً.", parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_active = group_protection.get(update.effective_chat.id, True)
    status_text = "مفعلة 🛡️" if is_active else "معطلة ⚠️"
    await update.message.reply_text(f"حالة حماية المجموعة حالياً: {status_text}")

# --- أوامر الحظر والكتم والتقييد ---

async def check_moderation_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دالة مساعدة للتحقق من صلاحية المشرف ووجود رد على رسالة"""
    if update.effective_chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("هذه الأوامر تعمل داخل المجموعات فقط.")
        return None

    if not await is_admin(update, context):
        await update.message.reply_text("عذراً، هذا الأمر للمشرفين فقط! 🚫")
        return None

    if not update.message.reply_to_message:
        await update.message.reply_text("⚠️ يرجى **الرد على رسالة العضو** لتنفيذ هذا الأمر.", parse_mode="Markdown")
        return None

    target_user = update.message.reply_to_message.from_user
    if target_user.id == context.bot.id:
        await update.message.reply_text("لا يمكنني تنفيذ هذا الإجراء على نفسي! 😅")
        return None

    if await is_admin(update, context, target_user.id):
        await update.message.reply_text("لا يمكن تنفيذ هذا الإجراء على مشرف آخر! 🛡️")
        return None

    return target_user

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حظر العضو من المجموعة"""
    target_user = await check_moderation_target(update, context)
    if not target_user:
        return

    try:
        await update.effective_chat.ban_member(target_user.id)
        await update.message.reply_text(
            f"🔨 تم حظر العضو {target_user.mention_html()} من المجموعة بنجاح.",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"فشل الحظر. تأكد من أن البوت يملك صلاحية حظر المستخدمين.\nالخطأ: {e}")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء حظر العضو"""
    target_user = await check_moderation_target(update, context)
    if not target_user:
        return

    try:
        await update.effective_chat.unban_member(target_user.id, only_if_banned=True)
        await update.message.reply_text(
            f"✅ تم إلغاء الحظر عن {target_user.mention_html()}، يمكنه الانضمام مجدداً.",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"فشل إلغاء الحظر: {e}")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """كتم العضو تماماً ومنعه من إرسال أي شيء"""
    target_user = await check_moderation_target(update, context)
    if not target_user:
        return

    permissions = ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False
    )

    try:
        await update.effective_chat.restrict_member(target_user.id, permissions=permissions)
        await update.message.reply_text(
            f"🔇 تم كتم العضو {target_user.mention_html()} ومنعه من الكتابة.",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"فشل الكتم. تأكد من صلاحيات البوت: {e}")

async def restrict_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تقييد العضو (يُسمح له بالنصوص فقط، ويُمنع من الوسائط والملصقات والروابط)"""
    target_user = await check_moderation_target(update, context)
    if not target_user:
        return

    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False, # يمنع الملصقات والصور المتحركة GIF
        can_add_web_page_previews=False
    )

    try:
        await update.effective_chat.restrict_member(target_user.id, permissions=permissions)
        await update.message.reply_text(
            f"⚠️ تم تقييد العضو {target_user.mention_html()} (مسموح له بإرسال الرسائل النصية فقط).",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"فشل التقييد. تأكد من صلاحيات البوت: {e}")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إلغاء الكتم والتقييد وإعادة الصلاحيات الافتراضية للمجموعة"""
    target_user = await check_moderation_target(update, context)
    if not target_user:
        return

    # استرجاع الصلاحيات الافتراضية للمجموعة
    default_permissions = update.effective_chat.permissions
    if not default_permissions:
        default_permissions = ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )

    try:
        await update.effective_chat.restrict_member(target_user.id, permissions=default_permissions)
        await update.message.reply_text(
            f"🔊 تم إلغاء الكتم والتقييد عن {target_user.mention_html()} واستعادة صلاحياته.",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"فشل إلغاء التقييد: {e}")

# --- نظام الحماية التلقائي ---

async def protect_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.chat or message.chat.type not in ['group', 'supergroup']:
        return

    chat_id = message.chat.id
    if not group_protection.get(chat_id, True):
        return

    if await is_admin(update, context):
        return

    # منع الروابط
    if message.entities:
        for entity in message.entities:
            if entity.type in ["url", "text_link", "mention"]:
                try:
                    await message.delete()
                    warning = await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"عذراً {message.from_user.mention_html()}، ممنوع إرسال الروابط في هذه المجموعة!",
                        parse_mode="HTML"
                    )
                    context.job_queue.run_once(lambda ctx: warning.delete(), 5, context=chat_id)
                except Exception as e:
                    logging.error(f"خطأ أثناء حذف الرابط: {e}")
                return

    # منع التوجيه
    if message.forward_from_chat or message.forward_from:
        try:
            await message.delete()
            warning = await context.bot.send_message(
                chat_id=chat_id,
                text=f"عذراً {message.from_user.mention_html()}، ممنوع إعادة التوجيه من القنوات هنا!",
                parse_mode="HTML"
            )
            context.job_queue.run_once(lambda ctx: warning.delete(), 5, context=chat_id)
        except Exception as e:
            logging.error(f"خطأ أثناء حذف رسالة التوجيه: {e}")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # أوامر الإدارة والحماية
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", start_command))
    application.add_handler(CommandHandler("enable", enable_protection))
    application.add_handler(CommandHandler("disable", disable_protection))
    application.add_handler(CommandHandler("status", status_command))

    # أوامر العقوبات (الحظر، الكتم، التقييد)
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("unban", unban_user))
    application.add_handler(CommandHandler("mute", mute_user))
    application.add_handler(CommandHandler("restrict", restrict_user))
    application.add_handler(CommandHandler("unmute", unmute_user))

    # مراقبة الرسائل التلقائية
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, protect_group))

    print("البوت يعمل الآن بكامل صلاحيات الحماية والإدارة...")
    application.run_polling()

if __name__ == '__main__':
    main()
