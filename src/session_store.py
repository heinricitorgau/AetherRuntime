from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredSession:
    session_id: str
    messages: tuple[str, ...]
    input_tokens: int
    output_tokens: int


DEFAULT_SESSION_DIR = Path('.port_sessions')


def save_session(session: StoredSession, directory: Path | None = None) -> Path:
    target_dir = directory or DEFAULT_SESSION_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f'{session.session_id}.json'
    path.write_text(json.dumps(asdict(session), indent=2))
    return path


def load_session(session_id: str, directory: Path | None = None) -> StoredSession:
    target_dir = directory or DEFAULT_SESSION_DIR
    session_path = target_dir / f'{session_id}.json'
    if not session_path.exists():
        raise FileNotFoundError(
            f"Session '{session_id}' not found at {session_path}. "
            "The session may have expired or the path is incorrect."
        )
    try:
        data = json.loads(session_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Session '{session_id}' has corrupted JSON at {session_path}: {exc}"
        ) from exc
    missing = [k for k in ('session_id', 'messages', 'input_tokens', 'output_tokens') if k not in data]
    if missing:
        raise ValueError(
            f"Session '{session_id}' is missing required fields: {missing}"
        )
    return StoredSession(
        session_id=data['session_id'],
        messages=tuple(data['messages']),
        input_tokens=data['input_tokens'],
        output_tokens=data['output_tokens'],
    )
