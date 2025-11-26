from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from helper_func.progress_bar import progress_bar
from helper_func.dbhelper import Database as Db
from helper_func.mux import softmux_vid, hardmux_vid, get_audio_tracks, dublaj_vid
from helper_func.thumb import get_thumbnail, get_duration, get_width_height
from config import Config
from plugins.forcesub import handle_force_subscribe
import time
import os
db = Db()

# Geçici ses seçimi ve kalite seçimi verisini saklamak için
user_audio_selection = {}
user_quality_selection = {}
user_waiting_custom_quality = {}  # Özel kalite girişi bekleyen kullanıcılar
user_dublaj_mode = {}  # Dublaj modunda olan kullanıcılar


@Client.on_message(filters.command('softmux') & filters.private)
async def softmux(bot, message, cb=False):
    me = await bot.get_me()

    chat_id = message.from_user.id
    og_vid_filename = db.get_vid_filename(chat_id)
    og_sub_filename = db.get_sub_filename(chat_id)
    text = ''
    if not og_vid_filename:
        text += 'İlk Önce Bir Video Dosyası Gönder\n'
    if not og_sub_filename:
        text += 'Altyazı Dosyası Gönder!'

    if not (og_sub_filename and og_vid_filename):
        await bot.send_message(chat_id, text)
        return

    # Ses track'lerini kontrol et
    audio_tracks = await get_audio_tracks(og_vid_filename)
    
    if len(audio_tracks) > 1:
        # Birden fazla ses varsa kullanıcıya sor
        user_audio_selection[chat_id] = {'mode': 'softmux', 'tracks': audio_tracks}
        
        buttons = []
        for i, track in enumerate(audio_tracks):
            lang = track.get('language', 'und')
            title = track.get('title', '')
            codec = track.get('codec', 'unknown')
            channels = track.get('channels', 0)
            
            # Buton metni oluştur
            btn_text = f"🎵 Ses {i+1}"
            if lang != 'und':
                btn_text += f" ({lang})"
            if title:
                btn_text += f" - {title}"
            btn_text += f" [{codec}, {channels}ch]"
            
            buttons.append([InlineKeyboardButton(
                btn_text,
                callback_data=f"audio_select_softmux_{i}"
            )])
        
        # Tüm sesleri kullan seçeneği
        buttons.append([InlineKeyboardButton(
            "🎼 Tüm Sesleri Kullan",
            callback_data="audio_select_softmux_all"
        )])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await bot.send_message(
            chat_id,
            "📢 Video dosyasında birden fazla ses track'i bulundu!\n\n"
            "Hangi ses track'ini kullanmak istersin?",
            reply_markup=reply_markup
        )
        return
    
    # Tek ses varsa veya ses yoksa direkt işleme devam et
    await process_softmux(bot, chat_id, og_vid_filename, og_sub_filename, audio_track_index=None)


@Client.on_message(filters.command('hardmux') & filters.private)
async def hardmux(bot, message, cb=False):
    me = await bot.get_me()
    
    chat_id = message.from_user.id
    og_vid_filename = db.get_vid_filename(chat_id)
    og_sub_filename = db.get_sub_filename(chat_id)
    text = ''
    if not og_vid_filename:
        text += 'Önce Video Dosyasını Gönder\n'
    if not og_sub_filename:
        text += 'Altyazı Dosyasını Gönder!'
    
    if not (og_sub_filename and og_vid_filename):
        return await bot.send_message(chat_id, text)
    
    # Önce kalite seçeneğini sor
    buttons = [
        [InlineKeyboardButton("📺 720P - 1500 Bitrate", callback_data="quality_720p_1500")],
        [InlineKeyboardButton("📺 720P - 2000 Bitrate", callback_data="quality_720p_2000")],
        [InlineKeyboardButton("📺 720P - 2500 Bitrate", callback_data="quality_720p_2500")],
        [InlineKeyboardButton("📺 1080P - 1500 Bitrate", callback_data="quality_1080p_1500")],
        [InlineKeyboardButton("📺 1080P - 2250 Bitrate", callback_data="quality_1080p_2250")],
        [InlineKeyboardButton("📺 1080P - 3000 Bitrate", callback_data="quality_1080p_3000")],
        [InlineKeyboardButton("⚙️ Özel Ayar Gir", callback_data="quality_custom")],
    ]
    
    reply_markup = InlineKeyboardMarkup(buttons)
    await bot.send_message(
        chat_id,
        "🎬 **Hardmux Kalite Seçenekleri**\n\n"
        "Lütfen istediğiniz çıktı kalitesini seçin:\n\n"
        "💡 **Öneriler:**\n"
        "• 720P seçenekleri: Daha hızlı, küçük dosya\n"
        "• 1080P seçenekleri: Daha yüksek kalite, büyük dosya\n"
        "• Yüksek bitrate: Daha net görüntü\n\n"
        "⚙️ **Özel Ayar:** 720P-3200 gibi istediğiniz değeri girebilirsiniz",
        reply_markup=reply_markup
    )


@Client.on_message(filters.command('dublaj') & filters.private)
async def dublaj(bot, message, cb=False):
    me = await bot.get_me()
    
    chat_id = message.from_user.id
    og_vid_filename = db.get_vid_filename(chat_id)
    
    if not og_vid_filename:
        await bot.send_message(chat_id, 'Önce Video Dosyasını Gönder!')
        return
    
    # Dublaj modu aktif
    user_dublaj_mode[chat_id] = True
    
    # Önce kalite seçeneğini sor
    buttons = [
        [InlineKeyboardButton("🎯 Orijinal (Sadece Ses Değiştir)", callback_data="quality_original")],
        [InlineKeyboardButton("📺 720P - 1500 Bitrate", callback_data="quality_720p_1500")],
        [InlineKeyboardButton("📺 720P - 2000 Bitrate", callback_data="quality_720p_2000")],
        [InlineKeyboardButton("📺 720P - 2500 Bitrate", callback_data="quality_720p_2500")],
        [InlineKeyboardButton("📺 1080P - 1500 Bitrate", callback_data="quality_1080p_1500")],
        [InlineKeyboardButton("📺 1080P - 2250 Bitrate", callback_data="quality_1080p_2250")],
        [InlineKeyboardButton("📺 1080P - 3000 Bitrate", callback_data="quality_1080p_3000")],
        [InlineKeyboardButton("⚙️ Özel Ayar Gir", callback_data="quality_custom")],
    ]
    
    reply_markup = InlineKeyboardMarkup(buttons)
    await bot.send_message(
        chat_id,
        "🎙️ **Dublaj - Ses Değiştirme**\n\n"
        "Lütfen istediğiniz çıktı kalitesini seçin:\n\n"
        "🎯 **Orijinal:** Video kalitesi korunur, sadece ses değişir (en hızlı)\n"
        "📺 **Diğer Seçenekler:** Video yeniden encode edilir\n\n"
        "💡 **Öneri:** Sadece ses değiştirmek için 'Orijinal' seçin",
        reply_markup=reply_markup
    )


# Callback handler for quality selection
@Client.on_callback_query(filters.regex('^quality_'))
async def quality_select_callback(bot, callback_query):
    chat_id = callback_query.from_user.id
    data = callback_query.data
    
    # Özel kalite girişi seçildiyse
    if data == 'quality_custom':
        await callback_query.message.delete()
        await callback_query.answer("Özel kalite girişi bekleniyor...")
        
        user_waiting_custom_quality[chat_id] = True
        
        await bot.send_message(
            chat_id,
            "⚙️ **Özel Kalite Ayarı**\n\n"
            "Lütfen istediğiniz kaliteyi şu formatta girin:\n\n"
            "**Format:** `ÇÖZÜNÜRlÜK-BİTRATE`\n\n"
            "**Örnekler:**\n"
            "• `720P-3200`\n"
            "• `1080P-4500`\n"
            "• `480P-1200`\n"
            "• `1440P-6000`\n\n"
            "💡 Bitrate değeri kbps cinsindendir.\n"
            "📝 Sadece sayı ve 'P' harfi kullanın."
        )
        return
    
    # Kalite seçimini parse et (quality_720p_1500)
    quality = data.replace('quality_', '')
    
    # Kalite seçimini kaydet
    user_quality_selection[chat_id] = quality
    
    await callback_query.message.delete()
    await callback_query.answer("Kalite seçildi! Ses seçimine geçiliyor...")
    
    await continue_with_audio_selection(bot, chat_id)


async def continue_with_audio_selection(bot, chat_id):
    """Ses seçimi adımına geç"""
    og_vid_filename = db.get_vid_filename(chat_id)
    
    # Dublaj modunda mı?
    is_dublaj_mode = user_dublaj_mode.get(chat_id, False)
    
    if not is_dublaj_mode:
        og_sub_filename = db.get_sub_filename(chat_id)
    else:
        og_sub_filename = None
    
    # Şimdi ses track'lerini kontrol et
    audio_tracks = await get_audio_tracks(og_vid_filename)
    
    if len(audio_tracks) > 1:
        # Birden fazla ses varsa kullanıcıya sor
        mode = 'dublaj' if is_dublaj_mode else 'hardmux'
        user_audio_selection[chat_id] = {'mode': mode, 'tracks': audio_tracks}
        
        buttons = []
        for i, track in enumerate(audio_tracks):
            lang = track.get('language', 'und')
            title = track.get('title', '')
            codec = track.get('codec', 'unknown')
            channels = track.get('channels', 0)
            
            # Buton metni oluştur
            btn_text = f"🎵 Ses {i+1}"
            if lang != 'und':
                btn_text += f" ({lang})"
            if title:
                btn_text += f" - {title}"
            btn_text += f" [{codec}, {channels}ch]"
            
            buttons.append([InlineKeyboardButton(
                btn_text,
                callback_data=f"audio_select_{mode}_{i}"
            )])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        
        if is_dublaj_mode:
            msg_text = "📢 Video dosyasında birden fazla ses track'i bulundu!\n\nHangi ses track'ini kullanmak istersin?"
        else:
            msg_text = "📢 Video dosyasında birden fazla ses track'i bulundu!\n\nHangi ses track'ini kullanmak istersin?\n\n⚠️ Not: Hardmux sadece tek ses kullanır."
        
        await bot.send_message(
            chat_id,
            msg_text,
            reply_markup=reply_markup
        )
    else:
        # Tek ses varsa direkt işleme başla
        quality = user_quality_selection.get(chat_id, '720p_2500')
        
        if is_dublaj_mode:
            await process_dublaj(bot, chat_id, og_vid_filename, audio_track_index=0, quality=quality)
        else:
            await process_hardmux(bot, chat_id, og_vid_filename, og_sub_filename, audio_track_index=0, quality=quality)
        
        # Temizlik
        if chat_id in user_quality_selection:
            del user_quality_selection[chat_id]
        if chat_id in user_dublaj_mode:
            del user_dublaj_mode[chat_id]


# Özel kalite girişi için message handler
@Client.on_message(filters.text & filters.private)
async def handle_custom_quality(bot, message):
    chat_id = message.from_user.id
    
    # Bu kullanıcı özel kalite girişi bekliyor mu?
    if chat_id not in user_waiting_custom_quality:
        return
    
    text = message.text.strip().upper()
    
    # Format kontrolü: 720P-3200 gibi
    import re
    pattern = r'^(\d+)P-(\d+)$'
    match = re.match(pattern, text)
    
    if not match:
        await bot.send_message(
            chat_id,
            "❌ Hatalı format!\n\n"
            "Lütfen şu formatta girin: `720P-3200`\n\n"
            "Tekrar deneyin:"
        )
        return
    
    resolution = match.group(1)
    bitrate = match.group(2)
    
    # Kaliteyi kaydet
    quality = f"{resolution}p_{bitrate}"
    user_quality_selection[chat_id] = quality
    
    # Bekleme durumunu temizle
    del user_waiting_custom_quality[chat_id]
    
    await bot.send_message(
        chat_id,
        f"✅ Özel kalite ayarlandı!\n\n"
        f"📺 Çözünürlük: {resolution}P\n"
        f"🎬 Bitrate: {bitrate} kbps\n\n"
        f"Ses seçimine geçiliyor..."
    )
    
    await continue_with_audio_selection(bot, chat_id)


# Callback handler for audio selection
@Client.on_callback_query(filters.regex('^audio_select_'))
async def audio_select_callback(bot, callback_query):
    chat_id = callback_query.from_user.id
    data = callback_query.data
    
    if chat_id not in user_audio_selection:
        await callback_query.answer("Oturum süresi doldu. Lütfen tekrar deneyin.", show_alert=True)
        return
    
    mode = user_audio_selection[chat_id]['mode']
    
    # Parse callback data
    if 'softmux' in data:
        if data.endswith('_all'):
            audio_index = None  # Tüm sesler
        else:
            audio_index = int(data.split('_')[-1])
        
        await callback_query.message.delete()
        await callback_query.answer("Ses seçildi! İşlem başlatılıyor...")
        
        og_vid_filename = db.get_vid_filename(chat_id)
        og_sub_filename = db.get_sub_filename(chat_id)
        
        await process_softmux(bot, chat_id, og_vid_filename, og_sub_filename, audio_index)
        
    elif 'hardmux' in data:
        audio_index = int(data.split('_')[-1])
        
        await callback_query.message.delete()
        await callback_query.answer("Ses seçildi! İşlem başlatılıyor...")
        
        og_vid_filename = db.get_vid_filename(chat_id)
        og_sub_filename = db.get_sub_filename(chat_id)
        
        # Kalite seçimini al
        quality = user_quality_selection.get(chat_id, '720p_2500')
        
        await process_hardmux(bot, chat_id, og_vid_filename, og_sub_filename, audio_index, quality)
        
        # Temizlik
        if chat_id in user_quality_selection:
            del user_quality_selection[chat_id]
    
    elif 'dublaj' in data:
        audio_index = int(data.split('_')[-1])
        
        await callback_query.message.delete()
        await callback_query.answer("Ses seçildi! İşlem başlatılıyor...")
        
        og_vid_filename = db.get_vid_filename(chat_id)
        
        # Kalite seçimini al
        quality = user_quality_selection.get(chat_id, 'original')
        
        await process_dublaj(bot, chat_id, og_vid_filename, audio_index, quality)
        
        # Temizlik
        if chat_id in user_quality_selection:
            del user_quality_selection[chat_id]
        if chat_id in user_dublaj_mode:
            del user_dublaj_mode[chat_id]
    
    # Temizlik
    if chat_id in user_audio_selection:
        del user_audio_selection[chat_id]


async def process_softmux(bot, chat_id, og_vid_filename, og_sub_filename, audio_track_index):
    """Softmux işlemini gerçekleştirir"""
    text = 'Dosyanıza soft altyazı uygulanıyor. Birkaç saniye içinde yapılır!'
    sent_msg = await bot.send_message(chat_id, text)

    softmux_filename = await softmux_vid(og_vid_filename, og_sub_filename, sent_msg, audio_track_index)
    if not softmux_filename:
        return

    final_filename = db.get_filename(chat_id)
    os.rename(Config.DOWNLOAD_DIR+'/'+softmux_filename, Config.DOWNLOAD_DIR+'/'+final_filename)
    video = os.path.join(Config.DOWNLOAD_DIR, final_filename)
    start_time = time.time()
    duration = get_duration(video)
    width, height = get_width_height(video)
    file_size = os.stat(video).st_size
    
    # Kullanıcının özel thumbnail'ini kontrol et
    custom_thumb = db.get_thumbnail(chat_id)
    if custom_thumb:
        # Özel thumbnail varsa indir
        thumb_path = await bot.download_media(custom_thumb, file_name=Config.DOWNLOAD_DIR + '/')
        thumb = thumb_path
    else:
        # Yoksa otomatik oluştur
        thumb = get_thumbnail(video, './' + Config.DOWNLOAD_DIR, duration / 4)
    
    if file_size > 2093796556:
        copy = await Config.userbot.send_document(
            chat_id=Config.PRE_LOG, 
            progress=progress_bar, 
            progress_args=(
                'Dosyan Yükleniyor!',
                sent_msg,
                start_time
            ), 
            document=video,
            thumb=thumb,
            caption=final_filename
        )
        text = 'Dosyan Başarı İle Yüklendi!\nGeçen Toplam Zaman : {} saniye'.format(round(time.time()-start_time))
        await sent_msg.edit(text)
        await bot.copy_message(
            chat_id=chat_id, 
            from_chat_id=Config.PRE_LOG, 
            message_id=copy.id
        )
    else:
        copy = await bot.send_document(
            chat_id=chat_id, 
            progress=progress_bar, 
            progress_args=(
                'Dosyan Yükleniyor!',
                sent_msg,
                start_time
            ), 
            document=video,
            thumb=thumb,
            caption=final_filename
        )
        text = 'Dosyan Başarı İle Yüklendi!\nGeçen Toplam Zaman : {} saniye'.format(round(time.time()-start_time))
        await sent_msg.edit(text)
    
    # Thumbnail temizliği
    if custom_thumb and thumb and os.path.exists(thumb):
        try:
            os.remove(thumb)
        except:
            pass
    
    path = Config.DOWNLOAD_DIR+'/'
    os.remove(path+og_sub_filename)
    os.remove(path+og_vid_filename)
    try:
        os.remove(path+final_filename)
    except:
        pass

    db.erase(chat_id)


async def process_hardmux(bot, chat_id, og_vid_filename, og_sub_filename, audio_track_index, quality='720p_2500'):
    """Hardmux işlemini gerçekleştirir"""
    quality_display = quality.replace('_', ' @ ')
    text = f'Dosyana Hard Altyazı Uygulanıyor.\n\n🎬 Kalite: {quality_display}\n\n⏳ Bu Uzun Sürebilir!'
    sent_msg = await bot.send_message(chat_id, text)

    hardmux_filename = await hardmux_vid(og_vid_filename, og_sub_filename, sent_msg, audio_track_index, quality)
    
    if not hardmux_filename:
        return
    
    # Orijinal dosya adını al ve .mp4 uzantısını zorla
    original_filename = db.get_filename(chat_id)
    
    # Dosya adının sonunu .mp4 yap
    if original_filename:
        # Uzantıyı kaldır ve .mp4 ekle
        base_name = os.path.splitext(original_filename)[0]
        final_filename = base_name + '.mp4'
    else:
        # hardmux_filename'den uzantıyı kaldır ve .mp4 ekle
        base_name = os.path.splitext(hardmux_filename)[0]
        final_filename = base_name + '.mp4'
    
    os.rename(Config.DOWNLOAD_DIR+'/'+hardmux_filename, Config.DOWNLOAD_DIR+'/'+final_filename)
    video = os.path.join(Config.DOWNLOAD_DIR, final_filename)
    duration = get_duration(video)
    width, height = get_width_height(video)
    start_time = time.time()
    file_size = os.stat(video).st_size
    
    # Kullanıcının özel thumbnail'ini kontrol et
    custom_thumb = db.get_thumbnail(chat_id)
    if custom_thumb:
        # Özel thumbnail varsa indir
        thumb_path = await bot.download_media(custom_thumb, file_name=Config.DOWNLOAD_DIR + '/')
        thumb = thumb_path
    else:
        # Yoksa otomatik oluştur
        thumb = get_thumbnail(video, './' + Config.DOWNLOAD_DIR, duration / 4)
    
    if file_size > 2093796556:
        copy = await Config.userbot.send_video(
            chat_id=Config.PRE_LOG, 
            progress=progress_bar,
            duration=duration,
            thumb=thumb,
            width=width,
            height=height,
            supports_streaming=True,
            progress_args=(
                'Dosyan Yükleniyor!',
                sent_msg,
                start_time
            ), 
            video=video,
            caption=final_filename
        )
        text = 'Dosya Başarı İle Yüklendi!\nToplam Geçen zaman : {} saniye'.format(round(time.time()-start_time))
        await sent_msg.edit(text)
        await bot.copy_message(
            chat_id=chat_id, 
            from_chat_id=Config.PRE_LOG, 
            message_id=copy.id
        )
    else:
        copy = await bot.send_video(
            chat_id=chat_id, 
            progress=progress_bar,
            duration=duration,
            thumb=thumb,
            width=width,
            height=height,
            supports_streaming=True,
            progress_args=(
                'Dosyan Yükleniyor!',
                sent_msg,
                start_time
            ), 
            video=video,
            caption=final_filename
        )
        text = 'Dosya Başarı İle Yüklendi!\nToplam Geçen zaman : {} saniye'.format(round(time.time()-start_time))
        await sent_msg.edit(text)
    
    # Thumbnail temizliği
    if custom_thumb and thumb and os.path.exists(thumb):
        try:
            os.remove(thumb)
        except:
            pass
            
    path = Config.DOWNLOAD_DIR+'/'
    os.remove(path+og_sub_filename)
    os.remove(path+og_vid_filename)
    try:
        os.remove(path+final_filename)
    except:
        pass
    db.erase(chat_id)


async def process_dublaj(bot, chat_id, og_vid_filename, audio_track_index, quality='original'):
    """Dublaj işlemini gerçekleştirir"""
    if quality == 'original':
        quality_display = "Orijinal (Sadece Ses Değişti)"
    else:
        quality_display = quality.replace('_', ' @ ')
    
    text = f'Dosyanın Sesi Değiştiriliyor.\n\n🎬 Kalite: {quality_display}\n\n⏳ Lütfen Bekleyin!'
    sent_msg = await bot.send_message(chat_id, text)

    dublaj_filename = await dublaj_vid(og_vid_filename, sent_msg, audio_track_index, quality)
    
    if not dublaj_filename:
        return
    
    # Orijinal dosya adını al ve .mp4 uzantısını zorla
    original_filename = db.get_filename(chat_id)
    
    # Dosya adının sonunu .mp4 yap
    if original_filename:
        # Uzantıyı kaldır ve .mp4 ekle
        base_name = '.'.join(original_filename.split('.')[:-1])
        final_filename = base_name + '.mp4'
    else:
        final_filename = dublaj_filename
    
    os.rename(Config.DOWNLOAD_DIR+'/'+dublaj_filename, Config.DOWNLOAD_DIR+'/'+final_filename)
    video = os.path.join(Config.DOWNLOAD_DIR, final_filename)
    duration = get_duration(video)
    width, height = get_width_height(video)
    start_time = time.time()
    file_size = os.stat(video).st_size
    
    # Kullanıcının özel thumbnail'ini kontrol et
    custom_thumb = db.get_thumbnail(chat_id)
    if custom_thumb:
        # Özel thumbnail varsa indir
        thumb_path = await bot.download_media(custom_thumb, file_name=Config.DOWNLOAD_DIR + '/')
        thumb = thumb_path
    else:
        # Yoksa otomatik oluştur
        thumb = get_thumbnail(video, './' + Config.DOWNLOAD_DIR, duration / 4)
    
    if file_size > 2093796556:
        copy = await Config.userbot.send_video(
            chat_id=Config.PRE_LOG, 
            progress=progress_bar,
            duration=duration,
            thumb=thumb,
            width=width,
            height=height,
            supports_streaming=True,
            progress_args=(
                'Dosyan Yükleniyor!',
                sent_msg,
                start_time
            ), 
            video=video,
            caption=final_filename
        )
        text = 'Dosya Başarı İle Yüklendi!\nToplam Geçen zaman : {} saniye'.format(round(time.time()-start_time))
        await sent_msg.edit(text)
        await bot.copy_message(
            chat_id=chat_id, 
            from_chat_id=Config.PRE_LOG, 
            message_id=copy.id
        )
    else:
        copy = await bot.send_video(
            chat_id=chat_id, 
            progress=progress_bar,
            duration=duration,
            thumb=thumb,
            width=width,
            height=height,
            supports_streaming=True,
            progress_args=(
                'Dosyan Yükleniyor!',
                sent_msg,
                start_time
            ), 
            video=video,
            caption=final_filename
        )
        text = 'Dosya Başarı İle Yüklendi!\nToplam Geçen zaman : {} saniye'.format(round(time.time()-start_time))
        await sent_msg.edit(text)
    
    # Thumbnail temizliği
    if custom_thumb and thumb and os.path.exists(thumb):
        try:
            os.remove(thumb)
        except:
            pass
            
    path = Config.DOWNLOAD_DIR+'/'
    os.remove(path+og_vid_filename)
    try:
        os.remove(path+final_filename)
    except:
        pass
    db.erase(chat_id)
