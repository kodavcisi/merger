import asyncio
import json
import os
from config import Config


async def get_subtitle_tracks(vid_filename):
    """
    Video dosyasındaki tüm altyazı track'lerini listeler.
    Returns: List of dict with subtitle track info
    """
    vid = Config.DOWNLOAD_DIR + '/' + vid_filename
    
    command = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        '-select_streams', 's',  # Sadece subtitle stream'leri seç
        vid
    ]
    
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        return []
    
    try:
        data = json.loads(stdout.decode('utf-8'))
        subtitle_tracks = []
        
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'subtitle':
                track_info = {
                    'index': stream.get('index', 0),
                    'language': stream.get('tags', {}).get('language', 'und'),
                    'title': stream.get('tags', {}).get('title', ''),
                    'codec': stream.get('codec_name', 'unknown')
                }
                subtitle_tracks.append(track_info)
        
        return subtitle_tracks
    except Exception as e:
        print(f"Error parsing subtitle tracks: {e}")
        return []


async def extract_subtitles(vid_filename, msg=None):
    """
    Video dosyasından tüm altyazıları .ass formatında çıkarır.
    Returns: List of extracted subtitle filenames
    """
    vid = Config.DOWNLOAD_DIR + '/' + vid_filename
    
    # Önce altyazı track'lerini tespit et
    subtitle_tracks = await get_subtitle_tracks(vid_filename)
    
    if not subtitle_tracks:
        return []
    
    extracted_files = []
    
    for i, track in enumerate(subtitle_tracks):
        # Dosya adı oluştur
        base_name = '.'.join(vid_filename.split('.')[:-1])
        lang = track.get('language', 'und')
        title = track.get('title', '')
        
        # Dosya adını oluştur
        if title:
            subtitle_filename = f"{base_name}.{lang}.{title}.ass"
        else:
            subtitle_filename = f"{base_name}.{lang}.{i}.ass"
        
        # Özel karakterleri temizle
        subtitle_filename = subtitle_filename.replace('/', '_').replace('\\', '_')
        subtitle_path = Config.DOWNLOAD_DIR + '/' + subtitle_filename
        
        # FFmpeg ile altyazıyı çıkar
        command = [
            'ffmpeg', '-hide_banner',
            '-i', vid,
            '-map', f'0:s:{i}',  # i'nci altyazı stream'ini seç
            '-c:s', 'ass',  # ASS formatına dönüştür
            '-y', subtitle_path
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            await process.wait()
            
            if process.returncode == 0 and os.path.exists(subtitle_path):
                extracted_files.append({
                    'filename': subtitle_filename,
                    'language': lang,
                    'title': title,
                    'index': i
                })
                
                if msg:
                    try:
                        await msg.edit(f"Altyazı çıkarılıyor... ({i+1}/{len(subtitle_tracks)})")
                    except:
                        pass
        except Exception as e:
            print(f"Error extracting subtitle {i}: {e}")
            continue
    
    return extracted_files


def clean_subtitle_file(subtitle_path):
    """
    Altyazı dosyasının ilk 13 satırını siler ve özel header ekler.
    """
    try:
        with open(subtitle_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # İlk 13 satırı atla
        if len(lines) > 13:
            lines = lines[13:]
        
        # Yeni header
        new_header = """[Script Info]
; This is an Advanced Sub Station Alpha v4+ script.
Title: 
ScriptType: v4.00+
PlayDepth: 0
ScaledBorderAndShadow: Yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,18,&H00FFFFFF,&H0000FFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,1,1,2,10,10,15,1


[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:10.00,Default,,0,0,0,,{\\an8}@BayGulencocuk @BayTyler\\Nİyi Seyirler Diler...
"""
        
        # Yeni içeriği yaz
        with open(subtitle_path, 'w', encoding='utf-8') as f:
            f.write(new_header)
            f.writelines(lines)
        
        return True
    except Exception as e:
        print(f"Error cleaning subtitle file: {e}")
        return False


async def extract_and_send_subtitles(bot, chat_id, vid_filename, msg=None):
    """
    Video dosyasından altyazıları çıkarır ve kullanıcıya gönderir.
    """
    # Altyazıları çıkar
    extracted_subs = await extract_subtitles(vid_filename, msg)
    
    if not extracted_subs:
        if msg:
            try:
                await msg.edit("❌ Video içinde altyazı bulunamadı.")
            except:
                pass
        else:
            await bot.send_message(chat_id, "❌ Video içinde altyazı bulunamadı.")
        return
    
    # Kullanıcıya bilgi ver
    info_text = f"✅ {len(extracted_subs)} altyazı dosyası bulundu!\n\n"
    for sub in extracted_subs:
        lang = sub['language']
        title = sub['title']
        info_text += f"📄 {lang}"
        if title:
            info_text += f" - {title}"
        info_text += "\n"
    
    if msg:
        try:
            await msg.edit(info_text + "\nAltyazılar gönderiliyor...")
        except:
            pass
    else:
        await bot.send_message(chat_id, info_text + "\nAltyazılar gönderiliyor...")
    
    # Altyazıları kullanıcıya gönder
    for sub in extracted_subs:
        subtitle_path = Config.DOWNLOAD_DIR + '/' + sub['filename']
        
        try:
            # Altyazı dosyasını temizle (ilk 13 satırı sil ve özel header ekle)
            clean_subtitle_file(subtitle_path)
            
            # Caption oluştur
            caption = f"🎬 Altyazı Dosyası\n\n"
            caption += f"🌐 Dil: {sub['language']}\n"
            if sub['title']:
                caption += f"📝 Başlık: {sub['title']}\n"
            caption += f"📋 Format: ASS"
            
            await bot.send_document(
                chat_id=chat_id,
                document=subtitle_path,
                caption=caption
            )
            
            # Dosyayı sil
            os.remove(subtitle_path)
        except Exception as e:
            print(f"Error sending subtitle {sub['filename']}: {e}")
            try:
                os.remove(subtitle_path)
            except:
                pass
    
    if msg:
        try:
            await msg.edit(f"✅ {len(extracted_subs)} altyazı dosyası başarıyla gönderildi!")
        except:
            pass
