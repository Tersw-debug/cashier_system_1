import getpass

import keyring
from keyring.errors import KeyringError


class KeyStoreError(Exception):
    pass


class KeyStore:
    """Keeps the MySQL password in the OS credential store (Windows Credential Manager).

    One-time setup on each machine:   python -m Database.keystore
    (MYSHOP_DB_PASSWORD in the environment overrides it.)
    """

    def __init__(self, service="MyShopERP", account="mysql-password"):
        self.service = service
        self.account = account

    def get_password(self) -> str:
        try:
            password = keyring.get_password(self.service, self.account)
        except KeyringError as e:
            raise KeyStoreError(f"Cannot access the OS credential store: {e}") from e
        if password is None:
            raise KeyStoreError(
                "No MySQL password is stored on this computer. "
                "Run:  python -m Database.keystore"
            )
        return password

    def set_password(self, password: str):
        try:
            keyring.set_password(self.service, self.account, password)
        except KeyringError as e:
            raise KeyStoreError(f"Cannot access the OS credential store: {e}") from e


if __name__ == "__main__":
    KeyStore().set_password(getpass.getpass("MySQL password for the MyShop user: "))
    print("Saved.")