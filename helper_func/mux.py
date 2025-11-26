from config import Config
import time
import re
import asyncio
import json


progress_pattern = re.compile(
    r'(frame|fps|size|time|bitrate|speed)\s*\=\s*(\S+)'
)


def parse_progress(line):
    items = {
        key: value for key, value in progress_pattern.findall(line)
    }
    if not items:
        return None
    return items

async def readlines(stream):
    pattern = re.compile(br'[\r\n]+')

    data = bytearray()
    while not stream.at_eof():
        lines = pattern.split(data)
        data[:] = lines.pop(-1)

        for line in lines:
            yield line

        data.extend(await stream.read(1024))

async def read_stderr(start, msg, process):
    last_update = -1
    async for line in readlines(process.stderr):
        line = line.decode('utf-8', errors='ignore')
        progress = parse_progress(line)
        if progress:
            now = time.time()
            elapsed = int(now - start)
            text = 'İLERLEME\n'
            text += 'Boyut : {}\n'.format(progress.get('size', 'N/A'))
            text += 'Süre : {}\n'.format(progress.get('time', 'N/A'))
            text += 'Hız : {}\n'.format(progress.get('speed', 'N/A'))

            # 5 saniyelik aralıkla güncelleme (throttle)
            if elapsed // 5 != last_update // 5:
                last_update = elapsed
                try:
                    await msg.edit(text=text)
                except Exception as e:
                    print(e)


async def get_audio_tracks(vid_filename):
    """
    Video dosyasındaki tüm ses track'lerini listeler.
    Returns: List of dict with track info [{'index': 0, 'language': 'eng', 'title': 'English'}, ...]
    """
    vid = Config.DOWNLOAD_DIR + '/' + vid_filename
    
    command = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        '-select_streams', 'a',  # Sadece audio stream'leri seç
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
        audio_tracks = []
        
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'audio':
                track_info = {
                    'index': stream.get('index', 0),
                    'language': stream.get('tags', {}).get('language', 'und'),
                    'title': stream.get('tags', {}).get('title', ''),
                    'codec': stream.get('codec_name', 'unknown'),
                    'channels': stream.get('channels', 0)
                }
                audio_tracks.append(track_info)
        
        return audio_tracks
    except Exception as e:
        print(f"Error parsing audio tracks: {e}")
        return []


async def softmux_vid(vid_filename, sub_filename, msg, audio_track_index=None):
    """
    audio_track_index: Seçilen ses track'inin index'i (None ise tüm sesler dahil edilir)
    """
    start = time.time()
    vid = Config.DOWNLOAD_DIR + '/' + vid_filename
    sub = Config.DOWNLOAD_DIR + '/' + sub_filename

    out_file = '.'.join(vid_filename.split('.')[:-1])
    output = out_file + '1.mkv'
    out_location = Config.DOWNLOAD_DIR + '/' + output
    
    # Altyazı formatını tespit et
    sub_ext = sub_filename.split('.').pop()
    # Eğer ass veya srt değilse, srt olarak ayarla
    if sub_ext not in ['ass', 'srt']:
        sub_ext = 'srt'
    
    command = [
        'ffmpeg', '-hide_banner',
        '-i', vid,
        '-i', sub,
    ]
    
    # Ses track seçimi
    if audio_track_index is not None:
        # Sadece seçilen ses track'ini al
        command.extend([
            '-map', '1:0',  # Altyazı
            '-map', '0:v:0',  # Video
            '-map', f'0:a:{audio_track_index}',  # Seçilen ses
        ])
    else:
        # Tüm track'leri al (eski davranış)
        command.extend([
            '-map', '1:0',
            '-map', '0',
        ])
    
    command.extend([
        '-disposition:s:0', 'default',
        '-c:v', 'copy',
        '-c:a', 'copy',
        '-c:s', sub_ext,
        '-y', out_location
    ])

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    await asyncio.wait([
        read_stderr(start, msg, process),
        process.wait(),
    ])

    if process.returncode == 0:
        elapsed = round(time.time() - start)
        await msg.edit('Altyazı Ekleme Başarı İle Tamamlandı!\n\nGeçen Süre : {} saniye'.format(elapsed))
    else:
        await msg.edit('Altyazı Eklenirken Bir Hata Oluştu!')
        return False
    await asyncio.sleep(2)
    return output


async def dublaj_vid(vid_filename, msg, audio_track_index=0, quality='original'):
    """
    Videodaki sesi değiştirir, altyazı kullanmaz.
    audio_track_index: Seçilen ses track'inin index'i
    quality: Kalite seçeneği (original, 720p_1500, 720p_2000, 720p_2500, 1080p_1500, 1080p_2250, 1080p_3000, veya özel)
    """
    start = time.time()
    vid = Config.DOWNLOAD_DIR + '/' + vid_filename

    out_file = '.'.join(vid_filename.split('.')[:-1])
    output = out_file + '1.mp4'
    out_location = Config.DOWNLOAD_DIR + '/' + output

    command = [
        'ffmpeg', '-hide_banner',
        '-i', vid,
    ]
    
    # Kalite ayarları
    if quality == 'original':
        # Orijinal değerler - sadece ses değiştir, video ve diğer sesler kopyalanır
        command.extend([
            '-map', '0:v:0',  # Video
            '-map', f'0:a:{audio_track_index}',  # Seçilen ses
            '-c:v', 'copy',  # Video kopyala (re-encode yok)
            '-c:a', 'aac',  # Ses AAC'ye dönüştür
            '-ac', '2',  # Stereo
            '-b:a', '192k',  # 192 kbps
        ])
    else:
        # Kaliteli encode
        try:
            parts = quality.split('_')
            resolution = parts[0].replace('p', '')
            bitrate = parts[1] + 'k'
        except:
            resolution = '720'
            bitrate = '2500k'
        
        command.extend([
            '-vf', f'scale=-2:{resolution}',
            '-c:v', 'libx264',
            '-b:v', bitrate,
            '-map', '0:v:0',
            '-map', f'0:a:{audio_track_index}',
            '-c:a', 'aac',
            '-ac', '2',
            '-b:a', '192k',
        ])
    
    command.extend([
        '-preset', 'fast',
        '-movflags', '+faststart',
        '-threads', '0',
        '-y', out_location
    ])

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    await asyncio.wait([
        read_stderr(start, msg, process),
        process.wait(),
    ])

    if process.returncode == 0:
        elapsed = round(time.time() - start)
        if quality == 'original':
            await msg.edit(f'Ses Değiştirme Başarı İle Tamamlandı!\n\nMod: Orijinal (Sadece Ses Değişti)\nGeçen Süre : {elapsed} saniye')
        else:
            resolution_display = quality.split('_')[0].replace('p', 'p')
            bitrate_display = quality.split('_')[1] + 'k'
            await msg.edit(f'Ses Değiştirme Başarı İle Tamamlandı!\n\nKalite: {resolution_display} @ {bitrate_display}\nGeçen Süre : {elapsed} saniye')
    else:
        await msg.edit('Ses Değiştirme İşleminde Bir Hata Oluştu!')
        return False

    await asyncio.sleep(2)
    return output



async def hardmux_vid(vid_filename, sub_filename, msg, audio_track_index=None, quality='720p_2500'):
    """
    audio_track_index: Seçilen ses track'inin index'i (None ise ilk ses kullanılır)
    quality: Kalite seçeneği (720p_1500, 720p_2000, 1080p_3000, veya özel format: 480p_1200)
    """
    start = time.time()
    vid = Config.DOWNLOAD_DIR + '/' + vid_filename
    sub = Config.DOWNLOAD_DIR + '/' + sub_filename

    out_file = '.'.join(vid_filename.split('.')[:-1])
    output = out_file + '1.mp4'
    out_location = Config.DOWNLOAD_DIR + '/' + output

    # Kalite ayarlarını parse et
    # Format: 720p_1500 veya custom: 1440p_6000
    try:
        parts = quality.split('_')
        resolution = parts[0].replace('p', '')  # '720p' -> '720'
        bitrate = parts[1] + 'k'  # '1500' -> '1500k'
    except:
        # Varsayılan değerler
        resolution = '720'
        bitrate = '2500k'

    command = [
        'ffmpeg', '-hide_banner',
        '-i', vid,
        '-vf', f'subtitles={sub},scale=-2:{resolution}',
        '-c:v', 'libx264',
        '-b:v', bitrate,
        '-map', '0:v:0',
        '-c:a', 'aac',
        '-ac', '2',
        '-b:a', '192k',
    ]
    
    # Ses track seçimi
    if audio_track_index is not None:
        command.extend(['-map', f'0:a:{audio_track_index}'])
    else:
        command.extend(['-map', '0:a:0'])  # İlk ses track'i
    
    command.extend([
        '-preset', 'fast',
        '-movflags', '+faststart',
        '-threads', '0',
        '-y', out_location
    ])

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    await asyncio.wait([
        read_stderr(start, msg, process),
        process.wait(),
    ])

    if process.returncode == 0:
        elapsed = round(time.time() - start)
        await msg.edit(f'Altyazı Ekleme Başarı İle Tamamlandı!\n\nKalite: {resolution}p @ {bitrate}\nGeçen Süre : {elapsed} saniye')
    else:
        await msg.edit('Altyazı Eklenirken Bir Hata Oluştu!')
        return False

    await asyncio.sleep(2)
    return output
