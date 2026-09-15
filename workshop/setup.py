"""Unlock the workshop credentials and verify the participant setup.

    uv run python -m workshop.setup

The encryption lives here too, because scripts/ship.py writes the bundle this
file reads and one pair of functions is easier to keep in step than two files.
"""

import argparse
import base64
import getpass
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]

FORMAT = "qdrant-legal-lab-credentials-v1"
AAD = FORMAT.encode()
SALT_BYTES = 16
NONCE_BYTES = 12
KEY_BYTES = 32
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1


def _b64(value):
    return base64.urlsafe_b64encode(value).decode()


def _unb64(value):
    return base64.urlsafe_b64decode(value.encode())


def _key(password, salt):
    if not isinstance(password, str) or not password:
        raise ValueError("password must not be empty")
    return Scrypt(
        salt=salt,
        length=KEY_BYTES,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
    ).derive(password.encode("utf-8"))


def encrypt(plaintext, password):
    """Return a self-contained authenticated ciphertext as UTF-8 JSON bytes."""
    if not isinstance(plaintext, bytes):
        raise TypeError("plaintext must be bytes")
    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    ciphertext = AESGCM(_key(password, salt)).encrypt(nonce, plaintext, AAD)
    return (
        json.dumps(
            {
                "format": FORMAT,
                "kdf": "scrypt-n32768-r8-p1",
                "cipher": "aes-256-gcm",
                "salt": _b64(salt),
                "nonce": _b64(nonce),
                "ciphertext": _b64(ciphertext),
            },
            indent=2,
            sort_keys=True,
        ).encode()
        + b"\n"
    )


def decrypt(bundle, password):
    """Authenticate and decrypt a bundle created by encrypt()."""
    data = json.loads(bundle)
    if (
        data.get("format") != FORMAT
        or data.get("kdf") != "scrypt-n32768-r8-p1"
        or data.get("cipher") != "aes-256-gcm"
    ):
        raise ValueError("unsupported credential bundle")
    salt = _unb64(data["salt"])
    nonce = _unb64(data["nonce"])
    ciphertext = _unb64(data["ciphertext"])
    if len(salt) != SALT_BYTES or len(nonce) != NONCE_BYTES:
        raise ValueError("invalid credential bundle")
    return AESGCM(_key(password, salt)).decrypt(nonce, ciphertext, AAD)



def install(root, password):
    encrypted = root / ".env.enc"
    destination = root / ".env"
    if destination.exists():
        return False
    if not encrypted.exists():
        raise ValueError("This participant package has no .env.enc credential bundle.")

    try:
        plaintext = decrypt(encrypted.read_bytes(), password)
        text = plaintext.decode("utf-8")
    except (InvalidTag, UnicodeDecodeError, ValueError, KeyError, TypeError):
        raise ValueError("That password did not unlock the credential bundle.") from None

    values = dotenv_values(stream=io.StringIO(text))
    if not values.get("QDRANT_URL") or not values.get("QDRANT_READONLY_API_KEY"):
        raise ValueError("The credential bundle is missing its read-only Qdrant connection.")
    if values.get("QDRANT_API_KEY"):
        raise ValueError("The credential bundle contains a write-capable key and was rejected.")
    if not values.get("OPENAI_API_KEY"):
        raise ValueError("The credential bundle is missing its OpenAI project key.")

    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=root, prefix=".env.", delete=False
        ) as temporary:
            temporary.write(text)
            temp_name = temporary.name
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, destination)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-preflight", action="store_true", help="unlock credentials without running checks"
    )
    args = parser.parse_args()

    destination = ROOT / ".env"
    if destination.exists():
        print("Workshop credentials are already unlocked on this laptop.")
    else:
        password = getpass.getpass("Workshop password: ")
        try:
            install(ROOT, password)
        except ValueError as exc:
            sys.exit(f"Setup failed: {exc}")
        print("Credentials unlocked. The local .env file is excluded from Git.", flush=True)

    if not args.no_preflight:
        print("\nChecking the workshop connection...\n", flush=True)
        result = subprocess.run([sys.executable, "-m", "workshop.run", "preflight"], cwd=ROOT)
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
