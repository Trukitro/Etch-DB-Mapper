import json
import os
import sys

def load_json_history(path):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Aviso: no se pudo leer el historial en '{path}' ({e}). Se empieza vacío.", file=sys.stderr)
            return {}
    return {}

def save_json_history(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

def format_duration_logic(seconds):
    if seconds < 60: return f"{seconds}s"
    minutes = int(seconds // 60)
    rem_seconds = round(seconds % 60, 2)
    return f"{minutes} min {rem_seconds}s"