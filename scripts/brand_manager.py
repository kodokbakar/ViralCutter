"""Brand preset management."""
import os
import json
from pathlib import Path

PRESETS_DIR = Path(__file__).parent.parent / "brand_presets"
SCHEMA_PATH = PRESETS_DIR / "schema.json"

def list_presets():
    """List all saved brand presets."""
    presets = []
    if PRESETS_DIR.exists():
        for f in PRESETS_DIR.glob("*.json"):
            if f.name != "schema.json":
                try:
                    with open(f, 'r') as fh:
                        data = json.load(fh)
                        presets.append({"name": data.get("name", f.stem), "file": f.name})
                except:
                    pass
    return presets

def load_preset(name):
    """Load a brand preset by name."""
    preset_path = PRESETS_DIR / f"{name}.json"
    if not preset_path.exists():
        return None
    with open(preset_path, 'r') as f:
        return json.load(f)

def save_preset(preset):
    """Save a brand preset."""
    PRESETS_DIR.mkdir(exist_ok=True)
    name = preset.get("name", "untitled")
    preset_path = PRESETS_DIR / f"{name}.json"
    with open(preset_path, 'w') as f:
        json.dump(preset, f, indent=2)
    return preset_path

def delete_preset(name):
    """Delete a brand preset."""
    preset_path = PRESETS_DIR / f"{name}.json"
    if preset_path.exists():
        preset_path.unlink()
        return True
    return False
