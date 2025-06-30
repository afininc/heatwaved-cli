import json
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet


class ConfigManager:
    def __init__(self, config_dir: Path | None = None):
        self.config_dir = config_dir or Path.cwd() / ".heatwaved"
        self.oci_dir = self.config_dir / ".oci"
        self.env_file = self.config_dir / "config.json"
        self.oci_config_file = self.oci_dir / "config"
        self._fernet = None

    def ensure_config_dir(self):
        """Create configuration directories if they don't exist."""
        self.config_dir.mkdir(exist_ok=True)
        self.oci_dir.mkdir(exist_ok=True)

        # Create .gitignore to exclude sensitive files
        gitignore_path = self.config_dir / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text("*\n!.gitignore\n")

    def _get_or_create_key(self) -> bytes:
        """Get or create encryption key."""
        key_file = self.config_dir / ".key"
        if key_file.exists():
            return key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            return key

    @property
    def fernet(self) -> Fernet:
        """Get Fernet instance for encryption."""
        if self._fernet is None:
            key = self._get_or_create_key()
            self._fernet = Fernet(key)
        return self._fernet

    def encrypt_value(self, value: str) -> str:
        """Encrypt a string value."""
        return self.fernet.encrypt(value.encode()).decode()

    def decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt an encrypted string value."""
        return self.fernet.decrypt(encrypted_value.encode()).decode()

    def save_db_config(self, config: dict[str, Any]):
        """Save database configuration with encrypted password."""
        # Make a copy to avoid modifying the original config
        config_to_save = config.copy()

        # Encrypt password
        if "password" in config_to_save:
            config_to_save["password"] = self.encrypt_value(config_to_save["password"])

        # Load existing config if any
        existing_config = {}
        if self.env_file.exists():
            existing_config = json.loads(self.env_file.read_text())

        # Update with new database config
        existing_config["database"] = config_to_save

        # Save to file
        self.env_file.write_text(json.dumps(existing_config, indent=2))

    def load_db_config(self) -> dict[str, Any] | None:
        """Load database configuration and decrypt password."""
        if not self.env_file.exists():
            return None

        config = json.loads(self.env_file.read_text())
        db_config = config.get("database")

        if db_config and "password" in db_config:
            db_config["password"] = self.decrypt_value(db_config["password"])

        return db_config

    def save_oci_config(self, config_text: str, parsed_config: dict[str, str]):
        """Save OCI configuration."""
        # Make a copy to avoid modifying the original
        parsed_config_copy = parsed_config.copy()

        # Update config_text with the correct key_file path if it was changed
        if "key_file" in parsed_config_copy:
            # Replace the key_file line in config_text with the updated path
            lines = config_text.split("\n")
            for i, line in enumerate(lines):
                if line.strip().startswith("key_file="):
                    lines[i] = f"key_file={parsed_config_copy['key_file']}"
                    break
            config_text = "\n".join(lines)

        # Save the updated config file
        self.oci_config_file.write_text(config_text)

        # Update the main config file with OCI info
        existing_config = {}
        if self.env_file.exists():
            existing_config = json.loads(self.env_file.read_text())

        existing_config["oci"] = {
            "config_path": str(self.oci_config_file),
            "configured": True,
            "profile": "DEFAULT",
        }

        self.env_file.write_text(json.dumps(existing_config, indent=2))

    def load_oci_config(self) -> dict[str, Any] | None:
        """Load OCI configuration."""
        if not self.env_file.exists():
            return None

        config = json.loads(self.env_file.read_text())
        return config.get("oci")

    def is_initialized(self) -> bool:
        """Check if configuration is initialized."""
        return self.config_dir.exists() and self.env_file.exists()
