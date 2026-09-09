import os
import json
import base64
from typing import List
from pydantic import BaseModel
from dotenv import load_dotenv
import anthropic

load_dotenv()

# ---------- Client ----------
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client

DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# ---------- Normal text output ----------
def llm_query(query: str, model: str = DEFAULT_MODEL):
    client = _get_client()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=0,
        messages=[
            {"role": "user", "content": query}
        ]
    )
    return response.content[0].text


# ---------- Structured output with schema ----------
def llm_structured(query: str, output_schema: BaseModel, model: str = DEFAULT_MODEL):
    """
    query: str -> user question
    output_schema: pydantic BaseModel -> defines structured output
    Returns: parsed pydantic model instance
    """
    client = _get_client()

    # Build JSON schema from pydantic model
    schema = output_schema.model_json_schema()
    schema_str = json.dumps(schema, indent=2)

    structured_prompt = f"""{query}

────────────────────────────────────────────
OUTPUT FORMAT (STRICT)
────────────────────────────────────────────

You MUST respond with ONLY valid JSON that conforms to this schema:

{schema_str}

Return ONLY the JSON object. No markdown, no explanation, no code fences.
Do NOT wrap in ```json``` tags.
Keep responses concise — do not add unnecessary whitespace or verbose justifications."""

    max_retries = 2
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=16384,
                temperature=0,
                messages=[
                    {"role": "user", "content": structured_prompt}
                ]
            )

            raw_text = response.content[0].text.strip()

            # Clean up potential markdown wrapping
            if raw_text.startswith("```"):
                lines = raw_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                raw_text = "\n".join(lines)

            # Handle truncated JSON — try to fix common issues
            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError:
                # Try to fix truncated JSON by closing open structures
                fixed = raw_text
                # Count open/close braces and brackets
                open_braces = fixed.count('{') - fixed.count('}')
                open_brackets = fixed.count('[') - fixed.count(']')

                # Remove trailing incomplete string/value
                if fixed.rstrip()[-1] not in ('}', ']', '"', 'e', 'l'):
                    # Truncated mid-value — find last complete field
                    last_comma = fixed.rfind(',')
                    if last_comma > 0:
                        fixed = fixed[:last_comma]

                # Close open structures
                fixed += ']' * max(0, open_brackets)
                fixed += '}' * max(0, open_braces)

                try:
                    parsed = json.loads(fixed)
                except json.JSONDecodeError:
                    if attempt < max_retries:
                        print(f"[llm_structured] JSON parse failed, retrying ({attempt+1}/{max_retries})...")
                        continue
                    raise

            return output_schema.model_validate(parsed)

        except Exception as e:
            last_error = e
            if attempt < max_retries:
                print(f"[llm_structured] Attempt {attempt+1} failed: {str(e)[:100]}, retrying...")
                continue
            raise last_error


# ---------- Image analysis ----------
def local_image_to_base64(path: str) -> tuple:
    """Convert local image file to base64 string and detect media type."""
    ext = path.lower().rsplit(".", 1)[-1]
    media_type_map = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    media_type = media_type_map.get(ext, "image/jpeg")

    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return b64, media_type


def analyze_images(image_paths: List[str], prompt: str, model: str = DEFAULT_MODEL):
    """
    Analyze images with Claude vision.
    Returns plain text response.
    """
    client = _get_client()

    # Build content blocks: images first, then prompt
    content = []

    for path in image_paths:
        b64_data, media_type = local_image_to_base64(path)
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": b64_data,
            }
        })

    content.append({
        "type": "text",
        "text": prompt
    })

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=0,
        messages=[
            {"role": "user", "content": content}
        ]
    )

    result_text = response.content[0].text
    print(f"[Claude Vision] Response length: {len(result_text)} chars")
    return result_text


# -------------------------------
# CLI Runner
# -------------------------------
if __name__ == "__main__":
    # Quick test
    print("Testing llm_query...")
    result = llm_query("Say 'hello' in 3 words")
    print(f"Result: {result}")

    print("\nTesting analyze_images...")
    image_paths = ['assets/front.png', 'assets/back.png']
    if os.path.exists(image_paths[0]):
        result = analyze_images(image_paths, "Describe this garment in 2 sentences.")
        print(f"Result: {result}")
    else:
        print("Test images not found, skipping vision test.")
