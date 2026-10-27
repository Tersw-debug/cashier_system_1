import hashlib
import hmac
import os


class PasswordHasher:
    N, R, P = 2**14, 8, 1

    @classmethod
    def hash(cls, password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=cls.N, r=cls.R, p=cls.P)
        return f"scrypt${salt.hex()}${digest.hex()}"

    @classmethod
    def verify(cls, password: str, stored: str) -> bool:
        try:
            _, salt_hex, digest_hex = stored.split("$")
            digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                                    n=cls.N, r=cls.R, p=cls.P)
            return hmac.compare_digest(digest.hex(), digest_hex)
        except Exception:
            return False