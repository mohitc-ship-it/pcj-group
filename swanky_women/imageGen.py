import os
import requests
import base64
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
IMAGE_MODEL_FLASH = os.getenv("IMAGE_MODEL_FLASH", "google/gemini-3.1-flash-image")  # Nano Banana 2 / Flash Image
IMAGE_MODEL_PRO   = os.getenv("IMAGE_MODEL_PRO", "google/gemini-3-pro-image")        # Nano Banana Pro Image
IMAGE_MODEL = IMAGE_MODEL_PRO if os.getenv("IMAGE_USE_PRO", "false").lower() == "true" else IMAGE_MODEL_FLASH


def _image_to_base64_url(image_path: str) -> str:
    """Convert image to base64 data URL."""
    ext = image_path.lower().rsplit(".", 1)[-1]
    mime_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
    mime = mime_map.get(ext, "image/png")
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _extract_and_save_image(data_url: str, output_filename: str) -> Optional[str]:
    """Extract base64 image from data URL and save to file."""
    try:
        b64_data = data_url.split(",", 1)[1]
        img_bytes = base64.b64decode(b64_data)
        img = Image.open(BytesIO(img_bytes))
        img.save(output_filename)
        print(f"Image saved as {output_filename}")
        return output_filename
    except Exception as e:
        print(f"Failed to decode image: {e}")
        return None


def generate_image(
    prompt: str,
    image_path: Optional[str] = None,
    output_filename: str = "generated_image.png",
    use_pro: bool = False,
    image_paths: Optional[list] = None,
    seed: Optional[int] = None,
) -> Optional[str]:
    """
    Generates image from text prompt or edits input image(s).
    - use_pro=False → uses gemini-flash-image (fast, cheap, first attempt)
    - use_pro=True  → uses gemini-3-pro-image (high quality, used on retry)
    - seed: deterministic seed for reproducible generations
    """
    model = IMAGE_MODEL_PRO if use_pro else IMAGE_MODEL_FLASH
    try:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            print("Warning: OPENROUTER_API_KEY not set")
            if os.path.exists(output_filename):
                return output_filename
            return None

        # Resolve seed from argument or environment
        if seed is None:
            env_seed = os.getenv("IMAGE_SEED")
            if env_seed and env_seed.isdigit():
                seed = int(env_seed)

        # Build message content
        content = []
        if image_paths:
            for p in image_paths:
                if p and os.path.exists(p):
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": _image_to_base64_url(p)}
                    })
        elif image_path and os.path.exists(image_path):
            content.append({
                "type": "image_url",
                "image_url": {"url": _image_to_base64_url(image_path)}
            })
        content.append({"type": "text", "text": prompt})

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content}]
        }
        if seed is not None:
            payload["seed"] = seed

        response = requests.post(
            OPENROUTER_BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180
        )

        if response.status_code != 200:
            print(f"OpenRouter error {response.status_code}: {response.text[:200]}")
            if os.path.exists(output_filename):
                print(f"Fallback: using cached {output_filename}")
                return output_filename
            return None

        result = response.json()
        message = result.get("choices", [{}])[0].get("message", {})

        # Method 1: Images in dedicated 'images' field (Nano Banana Pro format)
        images = message.get("images", [])
        if images:
            for img_entry in images:
                url = ""
                if isinstance(img_entry, dict):
                    if img_entry.get("type") == "image_url":
                        url = img_entry.get("image_url", {}).get("url", "")
                    elif "url" in img_entry:
                        url = img_entry["url"]
                elif isinstance(img_entry, str):
                    url = img_entry

                if url and url.startswith("data:"):
                    saved = _extract_and_save_image(url, output_filename)
                    if saved:
                        return saved

        # Method 2: Images in content array
        msg_content = message.get("content")
        if isinstance(msg_content, list):
            for part in msg_content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    if url.startswith("data:"):
                        saved = _extract_and_save_image(url, output_filename)
                        if saved:
                            return saved

        print("No image extracted from response")
        if os.path.exists(output_filename):
            print(f"Fallback: using cached {output_filename}")
            return output_filename
        return None

    except Exception as e:
        print(f"Image generation error: {e}")
        if os.path.exists(output_filename):
            print(f"Fallback: using cached {output_filename}")
            return output_filename
        return None
