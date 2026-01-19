import re
import os
from pathlib import Path
from typing import List
from .config import CONFIG

def normalize_lm_studio_url(url: str) -> str:
    """Normalize LM Studio URL to ensure proper /v1 suffix."""
    url = url.rstrip('/')
    if url.endswith('/v1'):
        return url
    url = re.sub(r'/v1/?$', '', url)
    return f"{url}/v1"

def sanitize_goal_for_filename(goal: str) -> str:
    """Convert goal string to safe filename."""
    safe = re.sub(r'[^\w\s-]', '', goal)
    safe = re.sub(r'\s+', '_', safe)
    return safe[:50].lower()

def get_safe_path(workspace: Path, path_str: str) -> Path:
    """Force a path to be relative to the workspace and prevent escapes."""
    if not path_str:
        return workspace
            
    p = Path(path_str).parts
    clean_parts = [part for part in p if part not in ["/", "\\", "..", "."] and ":" not in part]
    
    safe_path = workspace.joinpath(*clean_parts).resolve()
    
    if not str(safe_path).startswith(str(workspace)):
        return workspace / Path(path_str).name
            
    return safe_path

def clean_output(text: str) -> str:
    """Strip ANSI escape codes and control characters"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    text = ansi_escape.sub('', text)
    return "".join(ch for ch in text if ch.isprintable() or ch in '\n\t')

def parse_pytest_summary(output: str) -> str:
    """Extract a one-line summary from pytest output"""
    patterns = [
        r'(=+ (?:.*) in .*)', 
        r'(\d+ passed.*)',     
        r'(no tests ran.*)'    
    ]
    
    for p in patterns:
        match = re.search(p, output, re.IGNORECASE)
        if match:
            return match.group(1).strip('= ')
    
    return "Unknown test result"
