import asyncio
import os
import tempfile
import uuid

from aiogram import Bot
from aiogram.types import FSInputFile

from utils.progress import ProgressMessage

MAX_DURATION_SECONDS = 20
MAX_SIZE_MB = 8  # is se bada video compress hoga

# Ek time pe sirf ek video process hoti hai — ye hi "processing queue" hai.
_ffmpeg_lock = asyncio.Lock()


async def _get_duration(path: str) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    try:
        return float(stdout.decode().strip())
    except ValueError:
        return 0.0


async def _trim_video(input_path: str, output_path: str, seconds: int = MAX_DURATION_SECONDS) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", input_path, "-t", str(seconds),
        "-c:v", "libx264", "-c:a", "aac", output_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    return proc.returncode == 0 and os.path.exists(output_path)


async def _compress_video(input_path: str, output_path: str) -> bool:
    """CRF-based compression — quality thodi kam karke file size kaafi chhota kar deta hai."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", "libx264", "-crf", "30", "-preset", "fast",
        "-vf", "scale='min(720,iw)':-2",
        "-c:a", "aac", "-b:a", "96k",
        output_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    return proc.returncode == 0 and os.path.exists(output_path)


async def process_video(bot: Bot, chat_id: int, file_id: str, progress: ProgressMessage | None = None) -> str:
    """
    Video file_id leta hai, agar 20 sec se lamba hai to trim karta hai,
    aur naya file_id return karta hai (trimmed ho to naya, warna wahi purana).
    Temp files hamesha cleanup ho jaate hai (try/finally).
    """
    async with _ffmpeg_lock:  # queue: ek time pe ek hi video process hoga
        tmp_dir = tempfile.mkdtemp(prefix="welcomebot_")
        input_path = os.path.join(tmp_dir, f"in_{uuid.uuid4().hex}.mp4")
        output_path = os.path.join(tmp_dir, f"out_{uuid.uuid4().hex}.mp4")

        try:
            if progress:
                await progress.update(10, "🎬 Video download ho raha hai...")

            file = await bot.get_file(file_id)
            await bot.download_file(file.file_path, destination=input_path)

            if progress:
                await progress.update(35, "🎬 Video duration check ho raha hai...")

            duration = await _get_duration(input_path)

            if duration <= MAX_DURATION_SECONDS:
                size_mb = os.path.getsize(input_path) / (1024 * 1024)
                if size_mb <= MAX_SIZE_MB:
                    if progress:
                        await progress.update(100, f"✅ Video {duration:.0f}s hai, trim/compress ki zaroorat nahi.")
                    return file_id

                if progress:
                    await progress.update(60, f"🗜 Video {size_mb:.1f}MB hai, compress ho raha hai...")
                if await _compress_video(input_path, output_path):
                    if progress:
                        await progress.update(80, "⬆️ Compressed video upload ho raha hai...")
                    sent = await bot.send_video(
                        chat_id, FSInputFile(output_path), caption="🗜 Auto-compressed"
                    )
                    if progress:
                        await progress.update(100, "✅ Video compress ho gaya!")
                    return sent.video.file_id
                else:
                    if progress:
                        await progress.update(100, "⚠️ Compress fail hui, original video use ho raha hai.")
                    return file_id

            if progress:
                await progress.update(55, f"✂️ Video {duration:.0f}s hai, {MAX_DURATION_SECONDS}s tak trim ho raha hai...")

            success = await _trim_video(input_path, output_path, MAX_DURATION_SECONDS)
            if not success:
                if progress:
                    await progress.update(100, "⚠️ Trim fail hui, original video use ho raha hai.")
                return file_id

            # Trim ke baad bhi agar size bada hai, compress karo
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            if size_mb > MAX_SIZE_MB:
                if progress:
                    await progress.update(70, f"🗜 Video {size_mb:.1f}MB hai, compress ho raha hai...")
                compressed_path = os.path.join(tmp_dir, f"compressed_{uuid.uuid4().hex}.mp4")
                if await _compress_video(output_path, compressed_path):
                    os.remove(output_path)
                    output_path = compressed_path

            if progress:
                await progress.update(80, "⬆️ Trimmed video upload ho raha hai...")

            sent = await bot.send_video(
                chat_id, FSInputFile(output_path), caption="✂️ Auto-trimmed to 20s"
            )
            new_file_id = sent.video.file_id

            if progress:
                await progress.update(100, "✅ Video trim ho gaya!")

            return new_file_id

        finally:
            # Temp file cleanup — hamesha, chahe error aaye ya na aaye
            for p in (input_path, output_path):
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass
            try:
                os.rmdir(tmp_dir)
            except Exception:
                pass
