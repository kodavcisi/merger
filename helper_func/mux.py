from config import Config
import time
import re
import asyncio


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

async def softmux_vid(vid_filename, sub_filename, msg):

    start = time.time()
    vid = Config.DOWNLOAD_DIR + '/' + vid_filename
    sub = Config.DOWNLOAD_DIR + '/' + sub_filename

    out_file = '.'.join(vid_filename.split('.')[:-1])
    output = out_file + '1.mkv'
    out_location = Config.DOWNLOAD_DIR + '/' + output
    sub_ext = sub_filename.split('.').pop()
    command = [
        'ffmpeg', '-hide_banner',
        '-i', vid,
        '-i', sub,
        '-map', '1:0', '-map', '0',
        '-disposition:s:0', 'default',
        '-c:v', 'copy',
        '-c:a', 'copy',
        '-c:s', sub_ext,
        '-y', out_location
    ]

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


async def hardmux_vid(vid_filename, sub_filename, msg):

    start = time.time()
    vid = Config.DOWNLOAD_DIR + '/' + vid_filename
    sub = Config.DOWNLOAD_DIR + '/' + sub_filename

    out_file = '.'.join(vid_filename.split('.')[:-1])
    output = out_file + '1.mp4'
    out_location = Config.DOWNLOAD_DIR + '/' + output

    command = [
        'ffmpeg', '-hide_banner',
        '-i', vid,
        '-vf', 'subtitles=' + sub + ',scale=-2:720',
        '-c:v', 'libx264',
        '-b:v', '2300k',
        '-map', '0:v:0',
        '-c:a', 'aac',
        '-ac', '2',
        '-b:a', '192k',
        '-preset', 'fast',
        '-movflags', '+faststart',
        '-threads', '0',
        '-y', out_location
    ]

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
