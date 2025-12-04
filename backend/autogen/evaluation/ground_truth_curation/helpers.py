import re
import json
from pathlib import Path

def load_json_file(path: Path):
        """Load a single JSON value from a .json file with a few tolerances."""
        with open(path, "r", encoding="utf-8") as f:
            s = f.read().lstrip("\ufeff").strip()
            # Fast path: single JSON value
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass
            # Try to repair common concatenation like `}{` or `][`
            glued = re.sub(r'}\s*{', '},{', s)
            glued = re.sub(r']\s*\[', '],[', glued)
            try:
                return json.loads('[' + glued + ']')
            except json.JSONDecodeError as e:
                ctx = s[max(0, e.pos-120): e.pos+120]
                raise json.JSONDecodeError(
                    f"Cannot parse JSON at {path}. Nearby: {ctx!r}",
                    s, e.pos
                ) from e

def load_jsonl_file(path: Path):
    """Load NDJSON/JSONL (one JSON object per line, ignore blanks/comments)."""
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            t = line.strip()
            if not t or t.startswith("//"):
                continue
            # allow trailing comma at line end
            if t.endswith(","):
                t = t[:-1].rstrip()
            try:
                items.append(json.loads(t))
            except json.JSONDecodeError as e:
                # Give precise location for debugging
                raise json.JSONDecodeError(
                    f"Invalid JSON on line {lineno} of {path}: {t[:200]!r}",
                    t, e.pos
                ) from e
    return items

def load_any(path: Path):
    """Dispatch based on suffix; fall back to tolerant JSON loader."""
    suf = path.suffix.lower()
    if suf == ".jsonl" or suf == ".ndjson":
        return load_jsonl_file(path)
    elif suf == ".json":
        return load_json_file(path)
    else:
        # Default: try JSON first, then as JSONL
        try:
            return load_json_file(path)
        except Exception:
            return load_jsonl_file(path)