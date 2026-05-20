"""
VoxCPM2 Voice Generation Server

A standalone Flask server that generates TTS audio using VoxCPM2.
Clients POST a voice description + list of text prompts. The server generates
WAV files for each prompt and returns them as a ZIP archive.

Run on any CUDA-capable machine:
    pip install -r requirements.txt
    python server.py [--host 0.0.0.0] [--port 5123]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global model reference — loaded once on startup
_model = None
CACHE_DIR = Path(tempfile.gettempdir()) / "voxcpm2_cache"


def get_model():
    """Lazy-load the VoxCPM2 model (downloads weights on first run)."""
    global _model
    if _model is None:
        logger.info("Loading VoxCPM2 model (first request — may take a minute)...")
        from voxcpm import VoxCPM
        _model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
        logger.info("VoxCPM2 model loaded successfully")
    return _model


def _cache_key(voice_description: str, text: str) -> str:
    """Generate a deterministic cache key from voice description + text."""
    raw = f"{voice_description}\0{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _set_seed(voice_description: str):
    """Set the PyTorch random seed deterministically based on the voice description."""
    import torch
    import random
    
    # Hash the voice description to a stable 32-bit integer
    h = hashlib.sha256(voice_description.encode("utf-8")).hexdigest()
    seed = int(h[:8], 16) % (2**32 - 1)
    
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    random.seed(seed)
    logger.debug("Set generation seed deterministically to %d for voice: %s", seed, voice_description[:30])


def _generate_wav(voice_description: str, text: str) -> bytes:
    """
    Generate a WAV audio file for the given text with the voice description.

    Uses file-based caching to avoid re-generating identical requests.
    """
    cache_key = _cache_key(voice_description, text)
    cached_path = CACHE_DIR / f"{cache_key}.wav"

    if cached_path.exists() and cached_path.stat().st_size > 0:
        logger.debug("Cache hit for %s: %s", cache_key[:12], text[:40])
        return cached_path.read_bytes()

    model = get_model()

    # Format text with voice description in parentheses as VoxCPM2 expects
    if voice_description.strip():
        full_text = f"({voice_description}){text}"
        # Set seed deterministically based on voice description to ensure identical timbre/personality
        _set_seed(voice_description)
    else:
        full_text = text

    logger.info("Generating audio: %s", full_text[:80])
    wav = model.generate(
        text=full_text,
        cfg_value=2.0,
        inference_timesteps=10,
    )

    # Save to cache
    import soundfile as sf
    sf.write(str(cached_path), wav, model.tts_model.sample_rate)

    return cached_path.read_bytes()


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "model_loaded": _model is not None})


@app.route("/generate", methods=["POST"])
def generate():
    """
    Generate TTS audio for multiple prompts with a custom voice description.

    Request JSON:
    {
        "voice_description": "A warm, friendly male voice with a slight British accent",
        "prompts": {
            "prompt_key_1": "Text to speak for prompt 1",
            "prompt_key_2": "Text to speak for prompt 2"
        }
    }

    Returns: ZIP file containing WAV files named by prompt key.
    """
    data = request.get_json(force=True)
    voice_description = data.get("voice_description", "").strip()
    prompts = data.get("prompts", {})

    if not prompts:
        return jsonify({"error": "No prompts provided"}), 400

    if not voice_description:
        return jsonify({"error": "No voice_description provided"}), 400

    logger.info(
        "Generate request: %d prompts, voice='%s'",
        len(prompts),
        voice_description[:60],
    )

    # Generate all audio files
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for key, text in prompts.items():
            try:
                wav_bytes = _generate_wav(voice_description, text)
                zf.writestr(f"{key}.wav", wav_bytes)
            except Exception:
                logger.exception("Failed to generate audio for key=%s", key)
                return jsonify({"error": f"Generation failed for prompt '{key}'"}), 500

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name="voice_pack.zip",
    )


@app.route("/generate_single", methods=["POST"])
def generate_single():
    """
    Generate TTS audio for a single prompt.

    Request JSON:
    {
        "voice_description": "A warm, friendly male voice",
        "text": "The text to speak"
    }

    Returns: WAV audio file.
    """
    data = request.get_json(force=True)
    voice_description = data.get("voice_description", "").strip()
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"error": "No text provided"}), 400

    if not voice_description:
        return jsonify({"error": "No voice_description provided"}), 400

    try:
        wav_bytes = _generate_wav(voice_description, text)
        return send_file(
            io.BytesIO(wav_bytes),
            mimetype="audio/wav",
            as_attachment=True,
            download_name="output.wav",
        )
    except Exception:
        logger.exception("Failed to generate audio")
        return jsonify({"error": "Generation failed"}), 500


def main():
    parser = argparse.ArgumentParser(description="VoxCPM2 Voice Generation Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5123, help="Port (default: 5123)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="[%(asctime)s] %(levelname)-8s %(name)-20s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("VoxCPM2 server starting on %s:%d", args.host, args.port)
    logger.info("Cache directory: %s", CACHE_DIR)

    # Pre-load model at startup
    try:
        get_model()
    except Exception:
        logger.warning("Model pre-load failed; will retry on first request")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
