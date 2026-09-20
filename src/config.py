"""
Application Configuration Manager

Stores and retrieves persistent settings such as the global resume path,
target job search title, and automation parameters.
"""

import os
import json
from typing import Dict, Any

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "resume_path": "resumes/Test_Resume.pdf",
    "search_query": "Full stack developer",
    "search_location": "",
    "headless": False,
    "chatgpt_url": "https://chatgpt.com/g/g-p-example/c/example-chat-id",
    "pacing_min_seconds": 6,
    "pacing_max_seconds": 12
}


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json and database settings table."""
    merged = DEFAULT_CONFIG.copy()

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged.update(data)
        except Exception as e:
            print(f"Warning: Could not read config.json ({e}), using defaults.")

    # Override search_query, search_location, chatgpt_url, and headless_mode from database settings table
    try:
        from src.db import get_all_settings
        db_settings = get_all_settings()
        if "search_query" in db_settings and db_settings["search_query"]:
            merged["search_query"] = db_settings["search_query"]
        if "search_location" in db_settings and db_settings["search_location"] is not None:
            merged["search_location"] = db_settings["search_location"]
        if "chatgpt_url" in db_settings and db_settings["chatgpt_url"]:
            merged["chatgpt_url"] = db_settings["chatgpt_url"]
        if "headless_mode" in db_settings and db_settings["headless_mode"] is not None:
            val_bool = str(db_settings["headless_mode"]).lower() in ("true", "1", "yes")
            merged["headless_mode"] = val_bool
            merged["headless"] = val_bool
        elif "headless" in db_settings and db_settings["headless"] is not None:
            val_bool = str(db_settings["headless"]).lower() in ("true", "1", "yes")
            merged["headless_mode"] = val_bool
            merged["headless"] = val_bool
    except Exception:
        pass

    return merged


def save_config(new_config: Dict[str, Any]) -> Dict[str, Any]:
    """Save configuration to config.json and persist search_query, search_location, chatgpt_url & headless_mode in DB."""
    try:
        from src.db import set_setting
        if "search_query" in new_config and new_config["search_query"] is not None:
            set_setting("search_query", str(new_config["search_query"]))
        if "search_location" in new_config and new_config["search_location"] is not None:
            set_setting("search_location", str(new_config["search_location"]))
        if "chatgpt_url" in new_config and new_config["chatgpt_url"] is not None:
            set_setting("chatgpt_url", str(new_config["chatgpt_url"]))
        if "headless_mode" in new_config and new_config["headless_mode"] is not None:
            val_bool = bool(new_config["headless_mode"])
            set_setting("headless_mode", "true" if val_bool else "false")
            new_config["headless"] = val_bool
        elif "headless" in new_config and new_config["headless"] is not None:
            val_bool = bool(new_config["headless"])
            set_setting("headless_mode", "true" if val_bool else "false")
            new_config["headless_mode"] = val_bool
    except Exception as e:
        print(f"Warning: Could not save settings to database: {e}")

    current = load_config() if os.path.exists(CONFIG_FILE) else DEFAULT_CONFIG.copy()
    current.update(new_config)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
    except Exception as e:
        print(f"Error saving config.json: {e}")
    return current


def is_headless() -> bool:
    """Return whether browser automation should execute in headless mode."""
    cfg = load_config()
    return bool(cfg.get("headless_mode", cfg.get("headless", False)))
