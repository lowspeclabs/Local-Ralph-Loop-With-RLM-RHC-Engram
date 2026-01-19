import json
import re

def parse_json(text: str):
    """
    Extract and parse JSON from text.
    Handles Markdown code blocks and raw JSON.
    Returns parsed dict or list, or None if failed.
    """
    if not text:
        return None

    # Try to find JSON block
    # Look for ```json ... ```
    pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(pattern, text)
    if match:
        json_str = match.group(1)
    else:
        # Try to find raw JSON (starts with { or [)
        # Find first { or [
        start_idx = -1
        for i, char in enumerate(text):
            if char in '{[':
                start_idx = i
                break

        if start_idx != -1:
            # Find last } or ]
            end_idx = -1
            for i in range(len(text) - 1, start_idx - 1, -1):
                if text[i] in '}]':
                    end_idx = i + 1
                    break

            if end_idx != -1:
                json_str = text[start_idx:end_idx]
            else:
                json_str = text
        else:
            json_str = text

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None
