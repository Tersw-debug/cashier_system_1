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
            scheme, *parts = stored.split("$")
            if scheme == "scrypt":
                salt_hex, digest_hex = parts
                digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex),
                                        n=cls.N, r=cls.R, p=cls.P)
            elif scheme == "pbkdf2_sha256":          # written by the old admin-page code
                rounds, salt_hex, digest_hex = parts
                digest = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                             bytes.fromhex(salt_hex), int(rounds))
            else:
                return False
            return hmac.compare_digest(digest.hex(), digest_hex)
        except (ValueError, TypeError):
            return False

    @classmethod
    def needs_rehash(cls, stored: str) -> bool:
        return not stored.startswith("scrypt$")