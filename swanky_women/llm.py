import os
import json
import base64
from typing import List, Tuple, Optional
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

DEFAULT_MODEL = "claude-sonnet-4-6"

# Budget tokens for extended thinking (how much Claude can "think" per call)
THINKING_BUDGET = 5000


def _extract_thinking(response) -> str:
    """Extract extended thinking text from a Claude response, if present."""
    thinking_parts = []
    for block in response.content:
        if block.type == "thinking":
            thinking_parts.append(block.thinking)
    return "\n\n".join(thinking_parts) if thinking_parts else ""


def _extract_text(response) -> str:
    """Extract the main text output from a Claude response."""
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


# ---------- Normal text output ----------
def llm_query(query: str, model: str = DEFAULT_MODEL, enable_thinking: bool = False) -> Tuple[str, str]:
    """
    Returns (text_result, thinking_text).
    thinking_text is empty string when enable_thinking=False.
    """
    client = _get_client()

    kwargs = dict(
        model=model,
        max_tokens=8000 if enable_thinking else 4096,
        messages=[{"role": "user", "content": query}]
    )
    if enable_thinking:
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": THINKING_BUDGET}
        # (betas handled by SDK automatically or omitted)

    response = client.messages.create(**kwargs)
    text = _extract_text(response) or response.content[0].text
    thinking = _extract_thinking(response) if enable_thinking else ""
    return text, thinking


# ---------- Structured output with schema ----------
def llm_structured(
    query: str,
    output_schema: BaseModel,
    model: str = DEFAULT_MODEL,
    enable_thinking: bool = False,
) -> Tuple[BaseModel, str]:
    """
    Returns (parsed_model_instance, thinking_text).
    thinking_text is empty string when enable_thinking=False.
    """
    client = _get_client()

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
    last_thinking = ""

    for attempt in range(max_retries + 1):
        try:
            kwargs = dict(
                model=model,
                max_tokens=16384 if not enable_thinking else 20000,
                messages=[
                    {"role": "user", "content": structured_prompt},
                    # JSON prefill — forces model to start output with `{` (Anthropic JSON prompting best practice)
                    {"role": "assistant", "content": "{"},
                ],
            )
            if enable_thinking:
                kwargs["thinking"] = {"type": "enabled", "budget_tokens": THINKING_BUDGET}
                # Cannot use prefill with extended thinking — remove assistant prefill
                kwargs["messages"] = [{"role": "user", "content": structured_prompt}]

            response = client.messages.create(**kwargs)

            if enable_thinking:
                last_thinking = _extract_thinking(response)
                raw_text = _extract_text(response).strip()
            else:
                raw_text = response.content[0].text.strip()
                # Restore the `{` that was used as a prefill token
                if not raw_text.startswith("{") and not raw_text.startswith("["):
                    raw_text = "{" + raw_text

            # Clean up potential markdown wrapping
            if raw_text.startswith("```"):
                lines = raw_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                raw_text = "\n".join(lines)

            # Handle truncated JSON
            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError:
                fixed = raw_text
                open_braces = fixed.count('{') - fixed.count('}')
                open_brackets = fixed.count('[') - fixed.count(']')
                if fixed.rstrip()[-1] not in ('}', ']', '"', 'e', 'l'):
                    last_comma = fixed.rfind(',')
                    if last_comma > 0:
                        fixed = fixed[:last_comma]
                fixed += ']' * max(0, open_brackets)
                fixed += '}' * max(0, open_braces)
                try:
                    parsed = json.loads(fixed)
                except json.JSONDecodeError:
                    if attempt < max_retries:
                        print(f"[llm_structured] JSON parse failed, retrying ({attempt+1}/{max_retries})...")
                        continue
                    raise

            return output_schema.model_validate(parsed), last_thinking

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


def analyze_images(
    image_paths: List[str],
    prompt: str,
    model: str = DEFAULT_MODEL,
    enable_thinking: bool = False,
) -> Tuple[str, str]:
    """
    Analyze images with Claude vision.
    Returns (text_result, thinking_text).
    thinking_text is empty string when enable_thinking=False.
    """
    client = _get_client()

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
    content.append({"type": "text", "text": prompt})

    kwargs = dict(
        model=model,
        max_tokens=8000 if enable_thinking else 4096,
        messages=[{"role": "user", "content": content}]
    )
    if enable_thinking:
        kwargs["thinking"] = {"type": "enabled", "budget_tokens": THINKING_BUDGET}
        # (betas handled by SDK automatically or omitted)

    response = client.messages.create(**kwargs)

    if enable_thinking:
        text = _extract_text(response)
        thinking = _extract_thinking(response)
    else:
        text = response.content[0].text
        thinking = ""

    print(f"[Claude Vision] Response length: {len(text)} chars")
    return text, thinking


# -------------------------------
# CLI Runner
# -------------------------------
if __name__ == "__main__":
    print("Testing llm_query with thinking...")
    result, thinking = llm_query("Why is accuracy important in fashion tech packs?", enable_thinking=True)
    print(f"Thinking:\n{thinking[:300]}...")
    print(f"\nResult: {result[:200]}")
