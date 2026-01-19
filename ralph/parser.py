import json
import re
from typing import List, Dict, Any

class ResponseParser:
    """Helper class to extract and sanitize JSON from LLM responses."""

    @staticmethod
    def extract_json_objects(text: str) -> List[str]:
        """Extract all potential JSON objects from text using balanced brace counting."""
        objects = []
        i = 0
        
        while i < len(text):
            if text[i] == '{':
                start = i
                depth = 0
                in_string = False
                escape_next = False
                
                for j in range(i, len(text)):
                    char = text[j]
                    
                    if escape_next:
                        escape_next = False
                        continue
                    
                    if char == '\\' and in_string:
                        escape_next = True
                        continue
                    
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    
                    if not in_string:
                        if char == '{':
                            depth += 1
                        elif char == '}':
                            depth -= 1
                            if depth == 0:
                                objects.append(text[start:j+1])
                                i = j
                                break
            i += 1
        return objects

    @staticmethod
    def sanitize_json(json_str: str) -> str:
        """Clean up common LLM artifacts that break JSON parsing."""
        # Fix hallucinated triple quotes
        if '"""' in json_str:
            # Simple heuristic: find content between triple quotes and escape its newlines
            parts = json_str.split('"""')
            for i in range(1, len(parts), 2):
                parts[i] = parts[i].replace('\n', '\\n').replace('\r', '')
            json_str = '"'.join(parts)

        # Remove trailing commas
        json_str = re.sub(r',\s*([\]}])', r'\1', json_str)
        
        # Handle cases where LLM uses ' instead of " for keys
        if "'" in json_str and '"' not in json_str:
            json_str = json_str.replace("'", '"')
        
        return json_str

    @classmethod
    def parse_state_update(cls, content: str) -> Dict[str, Any]:
        """Robust extraction of state updates from LLM response."""
        json_blocks = []
        objs = cls.extract_json_objects(content)
        
        for obj in objs:
            sanitized = cls.sanitize_json(obj)
            try:
                block = json.loads(sanitized)
                if isinstance(block, dict):
                    json_blocks.append(block)
                    from .config import CONFIG
                    if CONFIG.get('DEBUG_MODE'):
                        print(f"[DEBUG] Found valid JSON block: {list(block.keys())}")
            except json.JSONDecodeError:
                continue
        
        if not json_blocks:
            result = {}
            obs_match = re.search(r'"observation"\s*:\s*"([^"]*)"', content)
            if obs_match: result['observation'] = obs_match.group(1)
            
            done_match = re.search(r'"done"\s*:\s*(true|false)', content)
            if done_match: result['done'] = (done_match.group(1).lower() == 'true')
            
            markdown_files = re.findall(r'(?:FILE|WRITE|EDIT|PATH):\s*([a-zA-Z0-9_\-\.\/]+)\s*\n\s*```[a-z]*\n([\s\S]*?)```', content, re.IGNORECASE)
            if markdown_files:
                result["execute"] = []
                for fname, fcontent in markdown_files:
                    result["execute"].append({"action": "write", "file": fname.strip(), "content": fcontent.strip()})
            
            return result

        merged = {}
        for block in json_blocks:
            if "action" in block:
                if "execute" not in merged: merged["execute"] = []
                merged["execute"].append(block)
            elif "execute" in block:
                if "execute" not in merged: merged["execute"] = []
                exec_val = block["execute"]
                if isinstance(exec_val, list): merged["execute"].extend(exec_val)
                else: merged["execute"].append(exec_val)
            
            for k in ["observation", "done", "artifacts", "context", "context_update", "artifact_update", "store_knowledge", "plan_update", "chat", "message"]:
                if k in block:
                    merged[k] = block[k]
        
        return merged
