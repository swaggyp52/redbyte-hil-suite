import json
import os
import logging

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "system_config.json")

class ConfigManager:
    _instance = None
    _config = {}

    @classmethod
    def load(cls, path=DEFAULT_CONFIG_PATH):
        try:
            with open(path, 'r') as f:
                cls._config = json.load(f)
            logger.info(f"Loaded system config from {path}")
        except FileNotFoundError:
            logger.warning(f"Config file not found at {path}, using defaults.")
            cls._config = {} # usage of defaults handled by getters
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config: {e}")
            cls._config = {}

    @classmethod
    def get(cls, key, default=None):
        return cls._config.get(key, default)

    @classmethod
    def get_channel_config(cls):
        return cls._config.get("channels", {})

    @classmethod
    def get_limits(cls):
        return cls._config.get("limits", {})

    @classmethod
    def get_opal_map(cls):
        return cls._config.get("opal_map", {})
