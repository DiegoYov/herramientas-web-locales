import asyncio
import json
import os
import re
import shutil
import tempfile
import sys
from typing import List, Dict, Any, Callable, Optional

FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE_PATH = shutil.which("ffprobe") or "ffprobe"

async def get_video_info(file_path: str) -> Dict[str, Any]:
    """Uses ffprobe to extract video metadata (duration, width, height, codecs, audio presence)."""
    cmd = [
        FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path
    ]
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise Exception(f"ffprobe error: {stderr.decode('utf-8', errors='ignore')}")
        
        data = json.loads(stdout.decode('utf-8', errors='ignore'))
        streams = data.get("streams", [])
        format_info = data.get("format", {})
        
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        
        duration = float(format_info.get("duration", 0.0))
        if duration == 0.0 and video_stream:
            duration = float(video_stream.get("duration", 0.0))
            
        width = int(video_stream.get("width", 0)) if video_stream else 0
        height = int(video_stream.get("height", 0)) if video_stream else 0
        r_frame_rate = video_stream.get("r_frame_rate", "30/1") if video_stream else "30/1"
        
        # Calculate fps
        try:
            num, den = map(int, r_frame_rate.split('/'))
            fps = num / den if den != 0 else 30.0
        except Exception:
            fps = 30.0

        return {
            "file_path": file_path,
            "filename": os.path.basename(file_path),
            "duration": duration,
            "width": width,
            "height": height,
            "fps": fps,
            "video_codec": video_stream.get("codec_name") if video_stream else None,
            "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
            "has_audio": audio_stream is not None,
            "size": int(format_info.get("size", os.path.getsize(file_path) if os.path.exists(file_path) else 0))
        }
    except Exception as e:
        return {
            "file_path": file_path,
            "filename": os.path.basename(file_path),
            "duration": 0.0,
            "width": 0,
            "height": 0,
            "fps": 30.0,
            "video_codec": None,
            "audio_codec": None,
            "has_audio": False,
            "size": os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            "error": str(e)
        }


async def merge_videos(
    input_files: List[str],
    output_file: str,
    target_resolution: str = "1080p", # "1080p", "720p", "4k", "original"
    preset: str = "fast",
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> str:
    """
    Concatenates multiple video files into output_file.
    Supports heterogeneous input files (varying resolutions, aspect ratios, framerates, missing audio).
    """
    if not input_files:
        raise ValueError("No input files provided for merging.")
    
    # 1. Gather metadata for all input videos
    infos = []
    total_duration = 0.0
    max_w, max_h = 1280, 720
    
    for idx, f in enumerate(input_files):
        if progress_callback:
            progress_callback(1.0 + (idx / len(input_files)) * 4.0, f"Analizando video {idx+1}/{len(input_files)}...")
        info = await get_video_info(f)
        infos.append(info)
        total_duration += info["duration"]
        if info["width"] > max_w:
            max_w = info["width"]
        if info["height"] > max_h:
            max_h = info["height"]

    # Resolution target selection
    res_map = {
        "1080p": (1920, 1080),
        "720p": (1280, 720),
        "4k": (3840, 2160),
    }
    
    if target_resolution in res_map:
        target_w, target_h = res_map[target_resolution]
    elif target_resolution == "original" and max_w > 0 and max_h > 0:
        # Round up to even numbers
        target_w = max_w if max_w % 2 == 0 else max_w + 1
        target_h = max_h if max_h % 2 == 0 else max_h + 1
    else:
        target_w, target_h = 1920, 1080

    target_fps = 30
    
    # 2. Build FFmpeg command with filter_complex
    cmd = [FFMPEG_PATH, "-y"]
    
    # Add input files
    for f in input_files:
        cmd.extend(["-i", f])
        
    filter_parts = []
    concat_inputs = []
    
    for i, info in enumerate(infos):
        v_in = f"[{i}:v]"
        v_out = f"[v{i}]"
        
        # Scale and pad to fit target aspect ratio maintaining original aspect ratio with black bars if needed
        scale_filter = (
            f"{v_in}scale=w={target_w}:h={target_h}:force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps={target_fps}{v_out}"
        )
        filter_parts.append(scale_filter)
        
        if info["has_audio"]:
            a_in = f"[{i}:a]"
            a_out = f"[a{i}]"
            audio_filter = f"{a_in}aformat=sample_rates=44100:channel_layouts=stereo{a_out}"
            filter_parts.append(audio_filter)
        else:
            # Generate silent audio matching video duration if file lacks audio
            a_out = f"[a{i}]"
            audio_filter = f"anullsrc=r=44100:cl=stereo,trim=duration={max(info['duration'], 1.0)}{a_out}"
            filter_parts.append(audio_filter)
            
        concat_inputs.append(f"{v_out}{a_out}")
        
    filter_complex = ";".join(filter_parts) + f";{''.join(concat_inputs)}concat=n={len(input_files)}:v=1:a=1[outv][outa]"
    
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", "22",
        "-c:a", "aac",
        "-b:a", "192k",
        "-progress", "pipe:1",
        output_file
    ])
    
    # 3. Launch process and monitor progress
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    regex_out_time = re.compile(r"out_time_us=(\d+)")
    
    while True:
        line = await proc.stdout.readline()
        if not line:
            break
        text = line.decode('utf-8', errors='ignore').strip()
        match = regex_out_time.search(text)
        if match and total_duration > 0:
            us = float(match.group(1))
            sec = us / 1_000_000.0
            percent = min(99.0, 5.0 + (sec / total_duration) * 94.0)
            if progress_callback:
                progress_callback(round(percent, 1), f"Procesando vídeo... {round(percent, 1)}%")

    _, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        err_msg = stderr.decode('utf-8', errors='ignore')
        raise Exception(f"FFmpeg falló al unificar vídeos:\n{err_msg[-1000:]}")
        
    if progress_callback:
        progress_callback(100.0, "¡Unificación completada con éxito!")
        
    return output_file
