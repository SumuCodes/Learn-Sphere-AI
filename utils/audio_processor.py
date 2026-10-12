"""
Audio Processing Utility
YouTube → MP3 → Waveform → Transcript
"""

import os
import subprocess
import numpy as np


def download_audio(youtube_url: str, output_dir: str = "downloads") -> str:
    """
    Download audio from YouTube URL using yt-dlp.
    Returns path to downloaded MP3 file.

    Install: pip install yt-dlp
    """
    os.makedirs(output_dir, exist_ok=True)
    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")

    # Use --print to capture the exact output file path
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--output", output_template,
        "--print", "after_move:filepath",   # Prints the final file path
        youtube_url
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp error: {result.stderr}")

    # The last non-empty line of stdout is the file path
    output_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not output_lines:
        raise RuntimeError("No output path from yt-dlp")
    
    output_path = output_lines[-1]
    if not output_path.endswith(".mp3"):
        raise FileNotFoundError("No MP3 file found after download")

    return output_path


def load_waveform(audio_path: str, sr: int = 22050):
    """
    Load audio file and return waveform array.

    Install: pip install librosa
    Returns: (waveform_array, sample_rate)
    """
    try:
        import librosa
        waveform, sample_rate = librosa.load(audio_path, sr=sr)
        return waveform, sample_rate
    except ImportError:
        raise ImportError("Install librosa: pip install librosa")


def get_waveform_stats(waveform: np.ndarray, sr: int) -> dict:
    """Return basic stats about the waveform."""
    duration = len(waveform) / sr
    return {
        "duration_seconds": round(duration, 2),
        "duration_formatted": f"{int(duration // 60)}:{int(duration % 60):02d}",
        "sample_rate": sr,
        "num_samples": len(waveform),
        "rms_energy": float(np.sqrt(np.mean(waveform ** 2))),
        "peak_amplitude": float(np.max(np.abs(waveform)))
    }


def transcribe_audio(audio_path: str, model_size: str = "base", language: str = None) -> dict:
    """
    Transcribe audio using OpenAI Whisper.

    Install: pip install openai-whisper
    Returns: {'text': str, 'segments': list, 'language': str}
    """
    try:
        import whisper
        model = whisper.load_model(model_size)
        options = {}
        if language:
            options["language"] = language
        result = model.transcribe(audio_path, **options)
        return result
    except ImportError:
        raise ImportError("Install whisper: pip install openai-whisper")


def split_audio_segments(audio_path: str, segment_duration: int = 30, output_dir: str = "segments"):
    """
    Split audio into fixed-duration segments using FFmpeg.
    Returns list of segment file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_pattern = os.path.join(output_dir, "segment_%03d.mp3")

    cmd = [
        "ffmpeg", "-i", audio_path,
        "-f", "segment",
        "-segment_time", str(segment_duration),
        "-c", "copy",
        output_pattern,
        "-y"
    ]

    subprocess.run(cmd, check=True, capture_output=True)
    segments = sorted([
        os.path.join(output_dir, f)
        for f in os.listdir(output_dir)
        if f.startswith("segment_")
    ])
    return segments


if __name__ == "__main__":
    print("Audio Processor Ready")
    print("Functions: download_audio, load_waveform, transcribe_audio")