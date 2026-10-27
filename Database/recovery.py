import base64

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# Paste the PUBLIC key printed by `recovery_tool.py keygen` between the quotes.
# (Public keys are safe to ship. The private key never leaves you.)
DEVELOPER_PUBLIC_KEY_PEM = """"""

_OAEP = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)


class RecoveryEscrow:
    def __init__(self, public_pem: str = DEVELOPER_PUBLIC_KEY_PEM):
        self.public_pem = public_pem.strip()

    def is_configured(self) -> bool:
        return bool(self.public_pem)

    def seal(self, key_hex: str) -> str:
        """Encrypt the database key so only the developer's private key can open it."""
        public = serialization.load_pem_public_key(self.public_pem.encode())
        return base64.b64encode(public.encrypt(key_hex.encode(), _OAEP)).decode("ascii")