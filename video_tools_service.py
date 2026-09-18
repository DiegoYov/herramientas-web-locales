import asyncio
import os
import re
import shutil
from typing import Optional, Callable, Dict, Any

FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE_PATH = shutil.which("ffprobe") or "ffprobe"

async def get_video_duration(file_path: str) -> float:
    """Helper to get video duration in seconds."""
    cmd = [
        FFPROBE_PATH,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        return float(stdout.decode().strip())
    except Exception:
        return 0.0


async def trim_video(
    input_path: str,
    start_time: str,  # e.g., "00:00:10" or "10"
    end_time: str,    # e.g., "00:01:30" or "90"
    output_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """Trims a video segment between start_time and end_time."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Vídeo no encontrado: {input_path}")

    if progress_callback:
        progress_callback(10.0, "Recortando segmento de vídeo...")

    cmd = [
        FFMPEG_PATH, "-y",
        "-ss", str(start_time),
        "-i", input_path,
        "-to", str(end_time),
        "-c", "copy",
        output_path
    ]

    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        # Fallback to re-encoding if stream copy fails
        cmd_reencode = [
            FFMPEG_PATH, "-y",
            "-ss", str(start_time),
            "-i", input_path,
            "-to", str(end_time),
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac",
            output_path
        ]
        proc = await asyncio.create_subprocess_exec(*cmd_reencode, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc.communicate()

    if progress_callback:
        progress_callback(100.0, "¡Vídeo recortado con éxito!")

    return output_path


async def adjust_volume(
    input_path: str,
    volume_factor: float,  # e.g., 0.0 (mute), 0.5 (50%), 1.0 (100%), 2.0 (200%), 3.0 (300%)
    output_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """Adjusts or boosts video audio volume without re-encoding video stream."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Vídeo no encontrado: {input_path}")

    if progress_callback:
        progress_callback(10.0, f"Ajustando volumen a {int(volume_factor * 100)}%...")

    if volume_factor == 0.0:
        # Mute audio completely
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-an",
            "-c:v", "copy",
            output_path
        ]
    else:
        # Adjust audio volume factor
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-filter:a", f"volume={volume_factor}",
            "-c:v", "copy",
            "-c:a", "aac",
            output_path
        ]

    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise Exception(f"Error al ajustar volumen: {stderr.decode('utf-8', errors='ignore')[-500:]}")

    if progress_callback:
        progress_callback(100.0, f"¡Volumen ajustado al {int(volume_factor * 100)}%!")

    return output_path


async def change_speed(
    input_path: str,
    speed_factor: float,  # 0.5, 0.75, 1.25, 1.5, 2.0
    output_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """Changes video playback speed (slow motion / fast forward)."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Vídeo no encontrado: {input_path}")

    if progress_callback:
        progress_callback(10.0, f"Cambiando velocidad del vídeo a {speed_factor}x...")

    pts_factor = 1.0 / speed_factor
    filter_complex = f"[0:v]setpts={pts_factor}*PTS[v];[0:a]atempo={speed_factor}[a]"

    cmd = [
        FFMPEG_PATH, "-y",
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac",
        output_path
    ]

    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise Exception(f"Error al cambiar velocidad: {stderr.decode('utf-8', errors='ignore')[-500:]}")

    if progress_callback:
        progress_callback(100.0, f"¡Velocidad ajustada a {speed_factor}x con éxito!")

    return output_path


async def extract_audio(
    input_path: str,
    audio_format: str,  # "mp3", "wav", "aac", "m4a"
    output_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """Extracts the audio track from a video file into an MP3 or WAV file."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Vídeo no encontrado: {input_path}")

    if progress_callback:
        progress_callback(10.0, f"Extrayendo pista de audio ({audio_format.upper()})...")

    fmt = audio_format.lower()
    codec = "libmp3lame" if fmt == "mp3" else "pcm_s16le" if fmt == "wav" else "aac"

    cmd = [
        FFMPEG_PATH, "-y",
        "-i", input_path,
        "-vn",
        "-c:a", codec,
        output_path
    ]

    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise Exception(f"Error al extraer audio: {stderr.decode('utf-8', errors='ignore')[-500:]}")

    if progress_callback:
        progress_callback(100.0, f"¡Audio extraído en formato {fmt.upper()} con éxito!")

    return output_path


async def rotate_video(
    input_path: str,
    rotation_degrees: int,  # 90, 180, 270
    output_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """Rotates a video by 90, 180, or 270 degrees."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Vídeo no encontrado: {input_path}")

    if progress_callback:
        progress_callback(10.0, f"Rotando vídeo {rotation_degrees}°...")

    if rotation_degrees == 90:
        transpose_filter = "transpose=1"
    elif rotation_degrees == 180:
        transpose_filter = "transpose=2,transpose=2"
    elif rotation_degrees == 270:
        transpose_filter = "transpose=2"
    else:
        transpose_filter = "transpose=1"

    cmd = [
        FFMPEG_PATH, "-y",
        "-i", input_path,
        "-vf", transpose_filter,
        "-c:a", "copy",
        output_path
    ]

    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise Exception(f"Error al rotar vídeo: {stderr.decode('utf-8', errors='ignore')[-500:]}")

    if progress_callback:
        progress_callback(100.0, f"¡Vídeo rotado {rotation_degrees}° con éxito!")

    return output_path


async def convert_video(
    input_path: str,
    target_format: str,  # "mp4", "webm", "avi", "mov", "gif"
    output_path: str,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """Converts a video file to another container format or animated GIF."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Vídeo no encontrado: {input_path}")

    fmt = target_format.lower()
    if progress_callback:
        progress_callback(10.0, f"Convirtiendo vídeo a formato {fmt.upper()}...")

    if fmt == "gif":
        # Create optimized animated GIF
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-vf", "fps=10,scale=480:-1:flags=lanczos",
            output_path
        ]
    elif fmt == "webm":
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-c:v", "libvpx-vp9", "-crf", "30", "-b:v", "0",
            "-c:a", "libopus",
            output_path
        ]
    else:
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", input_path,
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac",
            output_path
        ]

    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise Exception(f"Error al convertir vídeo: {stderr.decode('utf-8', errors='ignore')[-500:]}")

    if progress_callback:
        progress_callback(100.0, f"¡Vídeo convertido a {fmt.upper()} con éxito!")

    return output_path
