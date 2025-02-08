import os
import logging
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv

from logger import rome_logger

class Settings:
    def __init__(self):
        self._settings: Dict[str, str] = {}
        self._load_env_config()
        self._log_settings()

    def _load_env_config(self) -> None:
        """Load environment variables from .env file"""
        env_path = self._find_nearest_env_file()
        if env_path:
            load_dotenv(env_path)
            rome_logger.info(f"Loaded .env file from: {env_path}")
        
        # Load settings from environment
        self._settings = {
            "USE_OPENAI_EMBEDDING": os.getenv("USE_OPENAI_EMBEDDING"),
            "USE_OLLAMA_EMBEDDING": os.getenv("USE_OLLAMA_EMBEDDING"),
            "OLLAMA_EMBEDDING_MODEL": os.getenv("OLLAMA_EMBEDDING_MODEL", "mxbai-embed-large"),
            "CHARACTER_PATH": os.getenv("CHARACTER_PATH"),
        }

    def _find_nearest_env_file(self) -> Optional[Path]:
        """Find nearest .env file in parent directories"""
        current_dir = Path.cwd()
        while current_dir != current_dir.parent:
            env_path = current_dir / ".env"
            if env_path.exists():
                return env_path
            current_dir = current_dir.parent
        return None

    def _log_settings(self) -> None:
        """Log current settings"""
        rome_logger.info("Loading embedding settings:", {
            "USE_OPENAI_EMBEDDING": self._settings.get("USE_OPENAI_EMBEDDING"),
            "USE_OLLAMA_EMBEDDING": self._settings.get("USE_OLLAMA_EMBEDDING"),
            "OLLAMA_EMBEDDING_MODEL": self._settings.get("OLLAMA_EMBEDDING_MODEL")
        })

        rome_logger.info("Loading character settings:", {
            "CHARACTER_PATH": self._settings.get("CHARACTER_PATH"),
            "CWD": str(Path.cwd())
        })

    def get(self, key: str, default: str = None) -> Optional[str]:
        """Get setting value by key"""
        return self._settings.get(key, default)

    def set(self, key: str, value: str) -> None:
        """Set setting value"""
        self._settings[key] = value

    def has(self, key: str) -> bool:
        """Check if setting exists"""
        return key in self._settings

# Create singleton instance
settings = Settings()

# Example usage:
# from rome.core.settings import settings
# embedding_type = settings.get("USE_OPENAI_EMBEDDING")