import secrets
import keyring
from keyring.errors import KeyringError


class KeyStoreError(Exception):
    pass


class KeyStore:
    """Keeps the database encryption key in the OS credential store."""

    def __init__(self, service="MyShopERP", account="database-key"):
        self.service = service
        self.account = account

    def get_key(self, create=False) -> str:
        """Return the 64-hex-char key. Only creates a new one when create=True."""
        try:
            key = keyring.get_password(self.service, self.account)
            if key is None:
                if not create:
                    raise KeyStoreError(
                        "The database exists but its encryption key is missing "
                        "from the credential store."
                    )
                key = secrets.token_hex(32)
                keyring.set_password(self.service, self.account, key)
            return key
        except KeyringError as e:
            raise KeyStoreError(f"Cannot access the OS credential store: {e}") from e

    def set_key(self, key_hex: str):
        """Re-install a recovered key (used by the developer recovery tool)."""
        key_hex = key_hex.strip().lower()
        if len(key_hex) != 64 or any(ch not in "0123456789abcdef" for ch in key_hex):
            raise KeyStoreError("The key must be 64 hexadecimal characters.")
        try:
            keyring.set_password(self.service, self.account, key_hex)
        except KeyringError as e:
            raise KeyStoreError(f"Cannot access the OS credential store: {e}") from e