from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from helper_func.dbhelper import Database as Db
from config import Config

db = Db()


@Client.on_message(filters.private & filters.photo & ~filters.command(['showthumb', 'delthumb', 'setthumb', 'show_thumbnail', 'delete_thumbnail', 'set_thumbnail']), group=-1)
async def handle_photo_thumbnail(c: Client, m: Message):
    """Kullanıcı fotoğraf gönderdiğinde otomatik thumbnail olarak kaydet"""
    if not m.from_user:
        return await m.reply_text("❌ Seni tanımıyorum.")
    
    chat_id = m.from_user.id
    thumbnail = m.photo.file_id
    
    editable = await m.reply_text("📸 **Thumbnail işleniyor...**")
    
    # Thumbnail'i veritabanına kaydet
    db.set_thumbnail(chat_id, thumbnail)
    
    await editable.edit(
        "✅ **Özel Thumbnail Kaydedildi!**\n\n"
        "Artık tüm videolarınız bu thumbnail ile gönderilecek.\n\n"
        "📋 Komutlar:\n"
        "• /showthumb - Thumbnail'i göster\n"
        "• /delthumb - Thumbnail'i sil"
    )


@Client.on_message(filters.private & filters.command(["setthumb", "set_thumbnail"]), group=-1)
async def set_thumbnail_command(c: Client, m: Message):
    """Reply ile thumbnail ayarlama komutu"""
    if not m.from_user:
        return await m.reply_text("❌ Seni tanımıyorum.")
    
    # Reply kontrolü
    if not m.reply_to_message or not m.reply_to_message.photo:
        return await m.reply_text(
            "❌ Lütfen bir fotoğrafa reply yaparak bu komutu kullanın!\n\n"
            "**Veya:** Sadece fotoğraf gönderin, otomatik olarak thumbnail ayarlanır."
        )
    
    chat_id = m.from_user.id
    thumbnail = m.reply_to_message.photo.file_id
    
    editable = await m.reply_text("📸 **Thumbnail işleniyor...**")
    
    # Thumbnail'i veritabanına kaydet
    db.set_thumbnail(chat_id, thumbnail)
    
    await editable.edit(
        "✅ **Özel Thumbnail Kaydedildi!**\n\n"
        "Artık tüm videolarınız bu thumbnail ile gönderilecek.\n\n"
        "📋 Komutlar:\n"
        "• /showthumb - Thumbnail'i göster\n"
        "• /delthumb - Thumbnail'i sil"
    )


@Client.on_message(filters.private & filters.command(["delthumb", "delete_thumbnail"]), group=-1)
async def delete_thumbnail(c: Client, m: Message):
    """Thumbnail'i sil"""
    if not m.from_user:
        return await m.reply_text("❌ Seni tanımıyorum.")
    
    chat_id = m.from_user.id
    
    # Thumbnail'i sil
    db.set_thumbnail(chat_id, None)
    
    await m.reply_text(
        "🗑️ **Özel Thumbnail Silindi!**\n\n"
        "Artık videolarınız varsayılan thumbnail ile gönderilecek.\n\n"
        "💡 Yeni thumbnail ayarlamak için fotoğraf gönderin.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📸 Yeni Thumbnail Ayarla", callback_data="set_new_thumb_info")]
        ])
    )


@Client.on_message(filters.private & filters.command(["showthumb", "show_thumbnail"]), group=-1)
async def show_thumbnail(c: Client, m: Message):
    """Kayıtlı thumbnail'i göster"""
    if not m.from_user:
        return await m.reply_text("❌ Seni tanımıyorum.")
    
    chat_id = m.from_user.id
    
    # Thumbnail'i veritabanından al
    thumbnail = db.get_thumbnail(chat_id)
    
    if thumbnail:
        try:
            await c.send_photo(
                chat_id=chat_id,
                photo=thumbnail,
                caption=(
                    "📸 **Kayıtlı Thumbnail**\n\n"
                    "Bu thumbnail tüm videolarınızda kullanılacak."
                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑️ Thumbnail'i Sil", callback_data="deleteThumbnail")]
                ]),
                reply_to_message_id=m.id
            )
        except Exception as e:
            await m.reply_text(
                f"❌ **Thumbnail Gösterilemiyor!**\n\n"
                f"Hata: {str(e)}\n\n"
                f"Thumbnail ID: `{thumbnail}`\n\n"
                f"💡 Yeni bir fotoğraf göndererek thumbnail'i güncelleyin."
            )
    else:
        await m.reply_text(
            "❌ **Thumbnail Bulunamadı!**\n\n"
            "Henüz özel bir thumbnail ayarlamadınız.\n\n"
            "💡 Thumbnail ayarlamak için fotoğraf gönderin.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("ℹ️ Nasıl Ayarlanır?", callback_data="set_new_thumb_info")]
            ])
        )


# Callback handler for thumbnail deletion
@Client.on_callback_query(filters.regex('^deleteThumbnail$'), group=-1)
async def delete_thumbnail_callback(c: Client, callback_query):
    """Thumbnail silme callback'i"""
    chat_id = callback_query.from_user.id
    
    # Thumbnail'i sil
    db.set_thumbnail(chat_id, None)
    
    await callback_query.message.delete()
    await callback_query.answer("🗑️ Thumbnail silindi!", show_alert=True)
    
    await c.send_message(
        chat_id=chat_id,
        text=(
            "✅ **Thumbnail Başarıyla Silindi!**\n\n"
            "Artık videolarınız varsayılan thumbnail ile gönderilecek.\n\n"
            "💡 Yeni thumbnail ayarlamak için fotoğraf gönderin."
        )
    )


@Client.on_callback_query(filters.regex('^set_new_thumb_info$'), group=-1)
async def set_thumbnail_info(c: Client, callback_query):
    """Thumbnail ayarlama bilgisi"""
    await callback_query.answer()
    await callback_query.message.edit_text(
        "📸 **Thumbnail Nasıl Ayarlanır?**\n\n"
        "**1. Yöntem (Kolay):**\n"
        "• Sadece bir fotoğraf gönderin\n"
        "• Otomatik olarak thumbnail ayarlanır\n\n"
        "**2. Yöntem (Reply ile):**\n"
        "• Bir fotoğrafa reply yapın\n"
        "• `/setthumb` komutunu kullanın\n\n"
        "**Diğer Komutlar:**\n"
        "• `/showthumb` - Thumbnail'i göster\n"
        "• `/delthumb` - Thumbnail'i sil\n\n"
        "💡 **İpucu:** En iyi sonuç için 1280x720 boyutunda fotoğraf kullanın.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Geri", callback_data="close")]
        ])
    )
