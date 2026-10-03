import json
import os
import time
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


store_dir = Path(os.environ.get("BETTERCS_DATA_DIR", Path.home() / ".bettercs"))
key_path = store_dir / "session.key"
vault_path = store_dir / "sessions.enc"
session_ttl_seconds = 30 * 24 * 60 * 60


def _get_cipher():
    store_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(store_dir, 0o700)

    try:
        file_descriptor = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        key = key_path.read_bytes()
    else:
        key = Fernet.generate_key()
        with os.fdopen(file_descriptor, "wb") as key_file:
            key_file.write(key)

    os.chmod(key_path, 0o600)
    return Fernet(key)


def load_saved_sessions():
    if not vault_path.exists():
        return {}

    try:
        saved = json.loads(_get_cipher().decrypt(vault_path.read_bytes()))
    except (InvalidToken, json.JSONDecodeError, OSError, ValueError):
        return {}

    sessions = {}
    if not isinstance(saved, dict):
        return sessions

    for session_id, account in saved.items():
        if not isinstance(account, dict):
            continue
        token = account.get("token")
        username = account.get("username")
        expires_at = account.get("expiresAt", time.time() + session_ttl_seconds)
        if not isinstance(token, str) or not isinstance(username, str):
            continue
        if not isinstance(expires_at, (int, float)) or expires_at <= time.time():
            continue
        sessions[session_id] = {
            "token": token,
            "username": username,
            "repo": account.get("repo") if isinstance(account.get("repo"), str) else None,
            "branch": account.get("branch") if isinstance(account.get("branch"), str) else None,
            "expiresAt": expires_at,
            "tree": None,
            "base_files": {},
            "pending": {},
        }
    return sessions


def save_sessions(sessions):
    store_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(store_dir, 0o700)
    saved = {
        session_id: {
            "token": session["token"],
            "username": session["username"],
            "repo": session.get("repo"),
            "branch": session.get("branch"),
            "expiresAt": session["expiresAt"],
        }
        for session_id, session in sessions.items()
        if session.get("expiresAt", 0) > time.time()
    }

    if not saved:
        vault_path.unlink(missing_ok=True)
        return

    encrypted = _get_cipher().encrypt(json.dumps(saved).encode("utf-8"))
    temporary_path = vault_path.with_suffix(f".{os.getpid()}.tmp")
    try:
        file_descriptor = os.open(
            temporary_path,
            os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
            0o600,
        )
        with os.fdopen(file_descriptor, "wb") as vault_file:
            vault_file.write(encrypted)
        os.replace(temporary_path, vault_path)
    finally:
        temporary_path.unlink(missing_ok=True)