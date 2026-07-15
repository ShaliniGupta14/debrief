import base64
import uuid
from datetime import datetime


def encode_cursor(created_at: datetime, id_: uuid.UUID) -> str:
    payload = f"{created_at.isoformat()}|{id_}"
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        payload = base64.urlsafe_b64decode(cursor.encode()).decode()
        created_at_str, id_str = payload.split("|")
        return datetime.fromisoformat(created_at_str), uuid.UUID(id_str)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid cursor") from exc
