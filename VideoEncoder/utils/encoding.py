import asyncio
import json
import os
import subprocess
import time
from pathlib import Path

from .. import BASE_DIR, LOGGER, download_dir, encode_dir
from .database.access_db import db


def _run_probe(args):
    try:
        return subprocess.check_output(["ffprobe", "-v", "error", *args], stderr=subprocess.DEVNULL).decode().strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def get_codec(filepath, channel="v:0"):
    value = _run_probe(["-select_streams", channel, "-show_entries", "stream=codec_name,codec_tag_string", "-of", "default=nokey=1:noprint_wrappers=1", filepath])
    return value.split() if value else []


def get_media_streams(filepath):
    try:
        raw = subprocess.check_output(["ffprobe", "-hide_banner", "-v", "error", "-print_format", "json", "-show_streams", filepath], stderr=subprocess.DEVNULL)
        return json.loads(raw).get("streams", [])
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        LOGGER.warning("Unable to inspect media streams: %s", exc)
        return []


def _ffmpeg_filter_path(path):
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


async def extract_subs(filepath, msg, user_id):
    streams = [s for s in get_media_streams(filepath) if s.get("codec_type") == "subtitle"]
    if not streams or streams[0].get("codec_name") in {"hdmv_pgs_subtitle", "dvd_subtitle"}:
        return None
    output = os.path.join(encode_dir, f"{msg.id}.ass")
    proc = await asyncio.create_subprocess_exec("ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", filepath, "-map", "0:s:0", output, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0 or not os.path.isfile(output) or os.path.getsize(output) == 0:
        LOGGER.warning("Subtitle extraction failed: %s", stderr.decode(errors="replace")[-500:])
        return None
    return output


async def encode(filepath, message, msg, audio_map=None):
    if not os.path.isfile(filepath) or os.path.getsize(filepath) == 0:
        raise FileNotFoundError(filepath)
    if not get_media_streams(filepath):
        raise RuntimeError("FFprobe could not find any media streams")

    user_id = message.from_user.id
    ext = (await db.get_extensions(user_id) or "MKV").lower()
    if ext not in {"mp4", "mkv", "avi"}:
        ext = "mkv"
    output = os.path.join(encode_dir, f"{Path(filepath).stem}_{msg.id}.{ext}")
    progress_file = os.path.join(download_dir, f"progress_{msg.id}.txt")
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    Path(encode_dir).mkdir(parents=True, exist_ok=True)

    hevc = await db.get_hevc(user_id)
    bits = await db.get_bits(user_id)
    preset_map = {"uf": "ultrafast", "sf": "superfast", "vf": "veryfast", "f": "fast", "m": "medium", "s": "slow", "sl": "slower", "vs": "veryslow"}
    preset = preset_map.get(await db.get_preset(user_id), "veryfast")
    crf = max(0, min(51, int(await db.get_crf(user_id) or 22)))
    video_codec = "libx265" if hevc else "libx264"
    command = ["ffmpeg", "-hide_banner", "-y", "-i", filepath, "-map", "0:v:0?", "-c:v", video_codec, "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p10le" if bits else "yuv420p"]

    frame = await db.get_frame(user_id)
    frame_map = {"23.976": "24000/1001", "30": "30", "60": "60", "ntsc": "30000/1001", "pal": "25", "film": "24"}
    if frame in frame_map:
        command += ["-r", frame_map[frame]]
    if await db.get_tune(user_id):
        command += ["-tune", "animation"]
    if await db.get_aspect(user_id):
        command += ["-aspect", "16:9"]
    reframe = await db.get_reframe(user_id)
    if reframe in {"4", "8", "16"} and not hevc:
        command += ["-refs", reframe]
    if not hevc and await db.get_cabac(user_id):
        command += ["-coder", "1"]

    filters = []
    resolution = {"1080": "1920:1080", "720": "1280:720", "576": "768:576", "480": "852:480", "540": "960:540", "360": "640:360", "240": "426:240"}.get(await db.get_resolution(user_id))
    if resolution:
        filters.append(f"scale={resolution}:force_original_aspect_ratio=decrease")
    subtitle_path = os.path.join(encode_dir, f"{msg.id}.ass")
    if await db.get_hardsub(user_id) and os.path.isfile(subtitle_path):
        filters.append(f"subtitles='{_ffmpeg_filter_path(subtitle_path)}'")
    if filters:
        command += ["-vf", ",".join(filters)]

    streams = get_media_streams(filepath)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    if has_audio:
        audio = await db.get_audio(user_id)
        audio_codecs = {"dd": "ac3", "aac": "aac", "vorbis": "libvorbis", "alac": "alac", "opus": "libopus", "copy": "copy", "source": "copy"}
        command += ["-map", "0:a?", "-c:a", audio_codecs.get(audio, "aac")]
        bitrate = {"400": "400k", "320": "320k", "256": "256k", "224": "224k", "192": "192k", "160": "160k", "128": "128k"}.get(await db.get_bitrate(user_id))
        if bitrate and audio_codecs.get(audio, "aac") != "copy":
            command += ["-b:a", bitrate]
        sample = {"44.1K": "44100", "48K": "48000"}.get(await db.get_samplerate(user_id))
        if sample and audio_codecs.get(audio, "aac") != "copy":
            command += ["-ar", sample]
        channels = {"1.0": "1", "2.0": "2", "2.1": "3", "5.1": "6", "7.1": "8"}.get(await db.get_channels(user_id))
        if channels and audio_codecs.get(audio, "aac") != "copy":
            command += ["-ac", channels]
    if await db.get_subtitles(user_id) and any(s.get("codec_type") == "subtitle" for s in streams) and ext != "avi":
        command += ["-map", "0:s?", "-c:s", "mov_text" if ext == "mp4" else "copy"]
    if await db.get_metadata_w(user_id):
        command += ["-metadata", "title=Cantarellabots"]
    command += ["-map_metadata", "0", "-threads", str(max(1, os.cpu_count() or 1)), "-progress", progress_file, output]

    LOGGER.info("Starting FFmpeg for %s", os.path.basename(filepath))
    proc = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await proc.communicate()
    except asyncio.CancelledError:
        proc.kill()
        await proc.wait()
        raise
    if proc.returncode != 0 or not os.path.isfile(output) or os.path.getsize(output) == 0:
        error = stderr.decode(errors="replace").strip()
        LOGGER.error("FFmpeg failed (%s): %s", proc.returncode, error[-2000:])
        if os.path.exists(output):
            os.remove(output)
        return None
    if not get_media_streams(output):
        LOGGER.error("FFmpeg created an output that FFprobe cannot read")
        os.remove(output)
        return None
    return output


def get_thumbnail(in_filename, path, ttl):
    out = os.path.join(path, f"thumb_{int(time.time() * 1000)}.jpg")
    try:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(max(0, ttl)), "-i", in_filename, "-frames:v", "1", "-y", out], check=True, capture_output=True)
        return out if os.path.isfile(out) and os.path.getsize(out) else None
    except (OSError, subprocess.CalledProcessError):
        return None


def get_duration(filepath):
    try:
        return int(float(_run_probe(["-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filepath]) or 0))
    except ValueError:
        return 0


def get_width_height(filepath):
    value = _run_probe(["-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", filepath])
    try:
        return tuple(map(int, value.split("x")))
    except (ValueError, TypeError):
        return 1280, 720


async def media_info(saved_file_path):
    duration = get_duration(saved_file_path)
    bitrate = _run_probe(["-show_entries", "format=bit_rate", "-of", "default=noprint_wrappers=1:nokey=1", saved_file_path]) or None
    return duration or None, bitrate


async def handle_progress(proc, msg, message, filepath):
    await proc.wait()
