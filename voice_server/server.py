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
import json
import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from dotenv import load_dotenv

try:
    import google.generativeai as genai
except ModuleNotFoundError:
    genai = None

load_dotenv()

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global model reference — loaded once on startup
_model = None
CACHE_DIR = Path(tempfile.gettempdir()) / "voxcpm2_cache"

# Configure Gemini
gemini_key = os.getenv("GEMINI_API_KEY")
if not genai:
    if gemini_key and gemini_key != "your_gemini_api_key_here":
        logger.warning(
            "google-generativeai is not installed, so Gemini preprocessing is disabled even though GEMINI_API_KEY is set."
        )
    else:
        logger.warning("google-generativeai is not installed, so Gemini preprocessing is disabled.")
    gemini_key = None
elif gemini_key and gemini_key != "your_gemini_api_key_here":
    try:
        genai.configure(api_key=gemini_key)
        logger.info("Gemini API configured successfully")
    except Exception:
        logger.exception("Failed to configure Gemini API")
        gemini_key = None
else:
    logger.warning("GEMINI_API_KEY not found or set to default template value in environment. Preprocessing disabled.")
    gemini_key = None


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


def _preprocess_voice_description(voice_description: str) -> dict[str, Any]:
    """
    Optimize the user's custom voice description and predict dynamic hyperparameters using Gemini.
    """
    default_res = {
        "formatted_description": voice_description,
        "cfg_value": 2.0,
        "inference_timesteps": 10
    }

    if not gemini_key:
        return default_res

    try:
        model = genai.GenerativeModel("gemini-3.1-flash-lite")
        
        prompt = (
            "You are an expert prompt engineer and audio researcher working with VoxCPM2, "
            "an advanced multilingual zero-shot text-to-speech model. "
            "Your goal is to optimize a user's natural language voice description for the best "
            "TTS generation results, and predict optimal hyperparameters.\n\n"
            "VoxCPM2 description guidelines:\n"
            "- It expects a highly optimized, descriptive tagged string representing vocal traits.\n"
            "- Good descriptions specify: Gender, Age (e.g. young adult, middle-aged), Timbre/Quality "
            "(e.g. warm, clear, raspy, gravelly, bright), Tone (e.g. calm, friendly, encouraging, firm), "
            "Accent (e.g. American, British), and Pacing (e.g. natural pace, slow and articulate).\n\n"
            "Hyperparameter guidelines:\n"
            "- cfg_value: Classifier-Free Guidance scale (valid range: 1.0 to 5.0, default: 2.0). "
            "Raise this (e.g., 2.3 to 2.8) if the voice request is highly energetic, emotional, or requires "
            "extremely strong adherence to descriptive style. Lower this (e.g., 1.5 to 1.8) if the voice is "
            "exceptionally soft, calm, or quiet to avoid distortion/clipping.\n"
            "- inference_timesteps: ODE solver steps (valid range: 5 to 30, default: 10). "
            "Increase this (e.g., 12 to 18) if the requested voice requires professional crispness, clear "
            "diction, complex accents, or high-fidelity replication. Keep it default or lower (e.g. 8 to 10) "
            "for simple, standard voices where generation speed is more important.\n\n"
            "TASK:\n"
            f"Analyze this raw user description: \"{voice_description}\"\n\n"
            "Return a JSON object matching this schema exactly:\n"
            "{\n"
            "  \"formatted_description\": \"An optimized tag-like description string\",\n"
            "  \"cfg_value\": float,\n"
            "  \"inference_timesteps\": int\n"
            "}"
        )
        
        logger.info("Requesting Gemini voice preprocessing for: '%s'", voice_description[:60])
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        
        res = json.loads(response.text)
        
        formatted = res.get("formatted_description", voice_description)
        cfg = max(1.0, min(5.0, float(res.get("cfg_value", 2.0))))
        steps = max(5, min(30, int(res.get("inference_timesteps", 10))))
        
        logger.info(
            "Gemini preprocessing complete:\n  Raw: '%s'\n  Optimized: '%s'\n  cfg_value: %.2f, timesteps: %d",
            voice_description, formatted, cfg, steps
        )
        
        return {
            "formatted_description": formatted,
            "cfg_value": cfg,
            "inference_timesteps": steps
        }
    except Exception:
        logger.exception("Failed to run Gemini voice description preprocessing; falling back to defaults")
        return default_res


def _adapt_prompts_to_theme(voice_description: str, prompts: dict[str, str]) -> dict[str, str]:
    """
    Use Gemini to dynamically rewrite/adapt standard posture alert prompts to fit the theme
    or personality of the voice description, while retaining the correct corrective instruction.
    """
    if not gemini_key:
        return prompts

    try:
        import json as json_module
        model = genai.GenerativeModel("gemini-3.1-flash-lite")

        prompt = (
            "You are a creative script writer and dialogue designer for an AI posture coaching app. "
            "Your task is to take a dictionary of posture correction prompt alerts and rewrite the text of each alert "
            "to match the theme, personality, or archetype of this voice description: "
            f"\"{voice_description}\"\n\n"
            "CRITICAL RULES:\n"
            "1. You MUST retain the exact same postural correction advice (e.g., if it says to raise the head, "
            "the adapted alert must still clearly instruct them to raise their head. If it says to sit up/straighten, "
            "it must still clearly tell them to sit up/adjust shoulders).\n"
            "2. Make each response LONGER and more detailed (15-30 words each) to provide sufficient audio for voice cloning. "
            "Add descriptive phrases, additional context, or encouragement while maintaining the core instruction.\n"
            "3. Inject fitting vocabulary, slang, jargon, tone, and flavor matching the theme (e.g. for a cowboy: "
            "'partner', 'saddle up', 'chin high like a tall cactus', 'no slacking in the stirrups').\n"
            "4. Return a JSON object containing the exact same keys as the input, with the modified text as the values.\n\n"
            f"INPUT DICTIONARY:\n{json_module.dumps(prompts, indent=2)}\n\n"
            "Return the output as a valid JSON object matching the input structure exactly."
        )

        logger.info("Requesting Gemini script theme adaptation for: '%s'", voice_description[:60])
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )

        adapted = json_module.loads(response.text)

        # Verify the structure matches the input keys
        res = {}
        for k, original_text in prompts.items():
            res[k] = adapted.get(k, original_text).strip()

        logger.info("Successfully adapted %d prompts to theme '%s'", len(res), voice_description[:40])
        return res
    except Exception:
        logger.exception("Failed to adapt scripts using Gemini; falling back to original prompts")
        return prompts


def _generate_wav(
    raw_voice_description: str,
    formatted_description: str,
    original_text: str,
    adapted_text: str,
    cfg_value: float = 2.0,
    inference_timesteps: int = 10,
    reference_audio_path: str = None,
) -> bytes:
    """
    Generate a WAV audio file for the given text.

    Uses file-based caching. If a reference/cloned audio file is provided, uses it
    for voice cloning. Otherwise uses zero-shot voice design with the description.
    """
    cache_key = _cache_key(raw_voice_description, original_text)
    cached_path = CACHE_DIR / f"{cache_key}.wav"

    if cached_path.exists() and cached_path.stat().st_size > 0:
        logger.debug("Cache hit for %s: %s", cache_key[:12], original_text[:40])
        return cached_path.read_bytes()

    model = get_model()

    if reference_audio_path and Path(reference_audio_path).exists():
        # Voice cloning mode using uploaded reference audio
        logger.info("Generating via VoxCPM2 Voice Cloning using reference: %s", reference_audio_path)
        wav = model.generate(
            text=adapted_text,
            reference_wav_path=reference_audio_path,
            cfg_value=cfg_value,
            inference_timesteps=inference_timesteps,
        )
    else:
        # Zero-shot Voice Design mode (fallback or for description-based generation)
        if formatted_description.strip():
            full_text = f"({formatted_description}){adapted_text}"
            # Set seed deterministically based on raw voice description to ensure identical timbre/personality
            _set_seed(raw_voice_description)
        else:
            full_text = adapted_text

        logger.info("Generating via VoxCPM2 Voice Design: %s (cfg=%.2f, steps=%d)", full_text[:80], cfg_value, inference_timesteps)
        wav = model.generate(
            text=full_text,
            cfg_value=cfg_value,
            inference_timesteps=inference_timesteps,
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
        },
        "reference_audio_path": "/path/to/reference/audio.wav" (optional for voice cloning)
    }

    Returns: ZIP file containing WAV files named by prompt key.
    """
    data = request.get_json(force=True)
    voice_description = data.get("voice_description", "").strip()
    prompts = data.get("prompts", {})
    reference_audio_path = (data.get("reference_audio_path") or "").strip()

    if not prompts:
        return jsonify({"error": "No prompts provided"}), 400

    if not voice_description:
        return jsonify({"error": "No voice_description provided"}), 400

    logger.info(
        "Generate request: %d prompts, voice='%s', reference_audio_path='%s'%s",
        len(prompts),
        voice_description[:60],
        reference_audio_path[:60] if reference_audio_path else "NONE",
        f" (reference exists: {Path(reference_audio_path).exists()})" if reference_audio_path else "",
    )

    # Check if we have any files that actually need generating (i.e. not in cache)
    needed = {}
    for key, text in prompts.items():
        cache_key = _cache_key(voice_description, text)
        cached_path = CACHE_DIR / f"{cache_key}.wav"
        if not (cached_path.exists() and cached_path.stat().st_size > 0):
            needed[key] = text

    # Try to find a cached test audio for this voice_description to use as reference
    auto_reference_audio_path = ""
    if not reference_audio_path:
        test_text = "This is a preview of my voice. I will be monitoring your posture closely to help you stay aligned and healthy throughout your day."
        test_cache_key = _cache_key(voice_description, test_text)
        test_audio_path = CACHE_DIR / f"{test_cache_key}.wav"
        if test_audio_path.exists() and test_audio_path.stat().st_size > 0:
            auto_reference_audio_path = str(test_audio_path)
            logger.info("Auto-detected cached test audio for voice cloning: %s", auto_reference_audio_path)

    # Use explicit reference if provided, otherwise use auto-detected one
    final_reference_audio_path = reference_audio_path or auto_reference_audio_path

    # Preprocess description with Gemini once for the entire batch if generation is required
    if needed:
        prep = _preprocess_voice_description(voice_description)
        # Adapt all prompts to fit the custom theme/personality
        adapted_prompts = _adapt_prompts_to_theme(voice_description, prompts)
    else:
        prep = {
            "formatted_description": voice_description,
            "cfg_value": 2.0,
            "inference_timesteps": 10
        }
        adapted_prompts = prompts

    # Generate all audio files
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for key, text in prompts.items():
            try:
                wav_bytes = _generate_wav(
                    raw_voice_description=voice_description,
                    formatted_description=prep["formatted_description"],
                    original_text=text,
                    adapted_text=adapted_prompts[key],
                    cfg_value=prep["cfg_value"],
                    inference_timesteps=prep["inference_timesteps"],
                    reference_audio_path=final_reference_audio_path if final_reference_audio_path else None,
                )
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
        "text": "The text to speak",
        "reference_audio_path": "/path/to/reference/audio.wav" (optional for voice cloning)
    }

    Returns: WAV audio file.
    """
    data = request.get_json(force=True)
    voice_description = data.get("voice_description", "").strip()
    text = data.get("text", "").strip()
    reference_audio_path = (data.get("reference_audio_path") or "").strip()

    if not text:
        return jsonify({"error": "No text provided"}), 400

    if not voice_description:
        return jsonify({"error": "No voice_description provided"}), 400

    # Check if cached first
    cache_key = _cache_key(voice_description, text)
    cached_path = CACHE_DIR / f"{cache_key}.wav"

    if cached_path.exists() and cached_path.stat().st_size > 0:
        logger.debug("Cache hit for single generation: %s", text[:40])
        wav_bytes = cached_path.read_bytes()
    else:
        # Preprocess description using Gemini
        prep = _preprocess_voice_description(voice_description)
        # Adapt this single text prompt to fit the custom theme/personality
        adapted_res = _adapt_prompts_to_theme(voice_description, {"single": text})
        adapted_text = adapted_res.get("single", text)

        try:
            wav_bytes = _generate_wav(
                raw_voice_description=voice_description,
                formatted_description=prep["formatted_description"],
                original_text=text,
                adapted_text=adapted_text,
                cfg_value=prep["cfg_value"],
                inference_timesteps=prep["inference_timesteps"],
                reference_audio_path=reference_audio_path if reference_audio_path else None,
            )
        except Exception:
            logger.exception("Failed to generate audio")
            return jsonify({"error": "Generation failed"}), 500

    return send_file(
        io.BytesIO(wav_bytes),
        mimetype="audio/wav",
        as_attachment=True,
        download_name="output.wav",
    )


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
