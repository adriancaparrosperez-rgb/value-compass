from pathlib import Path
import yaml

def load_yaml(path: str):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))

def settings():
    return load_yaml("config/settings.yaml")

def universes():
    return load_yaml("config/universes.yaml")
