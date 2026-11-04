"""Read Jan Desktop threads and translate selected text messages to Open WebUI."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import os
import time
import uuid
from typing import Any

NAMESPACE = uuid.UUID("08f0d2b7-2efb-4615-8f35-ec33bbc9e551")


class PeriscopeError(Exception):
    """A safe, user-facing error."""


@dataclass(frozen=True)
class JanThread:
    id: str
    title: str
    model: str | None
    messages: tuple[dict[str, Any], ...]


def jan_data_dir() -> Path:
    custom = os.getenv("PERISCOPE_JAN_DATA")
    if custom:
        return Path(custom).expanduser().resolve()
    root = Path.home() / ".local/share"
    for name in ("Jan-nightly", "Jan"):
        candidate = root / name / "data"
        if (candidate / "threads").is_dir():
            return candidate
    return root / "Jan-nightly/data"


def thread_dirs(data_dir: Path) -> list[Path]:
    root = data_dir / "threads"
    if not root.is_dir():
        return []
    return sorted(
        (p for p in root.iterdir()
         if p.is_dir() and not p.is_symlink()
         and (p / "thread.json").is_file()
         and (p / "messages.jsonl").is_file()),
        key=lambda p: p.name,
    )


def _model_id(meta: Any) -> str | None:
    if isinstance(meta, str):
        return meta
    if isinstance(meta, dict):
        for key in ("id", "model", "name", "model_id"):
            if isinstance(meta.get(key), str) and meta[key]:
                return meta[key]
    return None


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        return _content_text(value.get("content", ""))
    if not isinstance(value, list):
        return ""
    result = []
    for block in value:
        if not isinstance(block, dict) or block.get("type", "text") not in ("text", "input_text", "output_text"):
            continue
        item = block.get("text", "")
        if isinstance(item, dict):
            item = item.get("value", "")
        if isinstance(item, str):
            result.append(item)
    return "\n".join(result)


def read_thread(folder: Path) -> JanThread:
    try:
        meta = json.loads((folder / "thread.json").read_text(encoding="utf-8"))
        thread_id = meta.get("id") or folder.name
        if not isinstance(thread_id, str) or not thread_id:
            raise PeriscopeError("Invalid thread id")
        title = meta.get("title") or thread_id
        model = _model_id(meta.get("model"))
        messages = []
        with (folder / "messages.jsonl").open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict) or record.get("role") not in ("user", "assistant"):
                    continue
                content = _content_text(record.get("content"))
                if not content.strip():
                    continue
                messages.append({
                    "id": str(record.get("id") or f"line-{line_number}"),
                    "role": record["role"],
                    "content": content,
                    "created_at": record.get("created_at") or record.get("created") or 0,
                    "model": _model_id(record.get("model")) or model,
                })
        return JanThread(thread_id, str(title), model, tuple(messages))
    except (OSError, ValueError, TypeError) as exc:
        raise PeriscopeError(f"Could not read Jan thread {folder.name}: {exc}") from exc


def locate_thread(data_dir: Path, thread_id: str) -> JanThread:
    # Never permit ../ traversal or an absolute path from a user-provided ID.
    for folder in thread_dirs(data_dir):
        if folder.name == thread_id:
            return read_thread(folder)
    raise PeriscopeError(f"Jan Desktop thread not found: {thread_id}")


def _seconds(value: Any) -> int:
    try:
        number = float(value)
        if number > 1e11:
            number /= 1000
        return int(number) if number >= 0 else int(time.time())
    except (TypeError, ValueError):
        return int(time.time())


def as_openwebui_chat(thread: JanThread) -> dict[str, Any]:
    history: dict[str, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    prior: str | None = None
    for index, source in enumerate(thread.messages):
        mid = str(uuid.uuid5(NAMESPACE, f"{thread.id}\0{source['id']}\0{index}"))
        role = source["role"]
        item: dict[str, Any] = {
            "id": mid,
            "parentId": prior,
            "childrenIds": [],
            "role": role,
            "content": source["content"],
            "timestamp": _seconds(source.get("created_at")),
        }
        if role == "assistant":
            item["done"] = True
            if source.get("model"):
                item["model"] = source["model"]
        if prior:
            history[prior]["childrenIds"].append(mid)
        history[mid] = item
        ordered.append(item)
        prior = mid
    model = thread.model or os.getenv("PERISCOPE_DEFAULT_MODEL") or ""
    if not model:
        model = next((x["model"] for x in reversed(ordered) if x.get("model")), "")
    return {
        "title": thread.title,
        "models": [model] if model else [],
        "messages": ordered,
        "history": {"currentId": prior, "messages": history},
        "params": {},
    }


def state_directory() -> Path:
    return Path(os.getenv("PERISCOPE_STATE_DIR", "~/.local/share/periscope")).expanduser()


def load_state(folder: Path) -> dict[str, Any]:
    file = folder / "links.json"
    if not file.exists():
        return {"version": 1, "links": {}}
    try:
        value = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("links"), dict):
            raise ValueError("Unsupported registry format")
        return value
    except (OSError, ValueError) as exc:
        raise PeriscopeError(f"Invalid link registry at {file}: {exc}") from exc


def save_state(folder: Path, state: dict[str, Any]) -> None:
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(folder, 0o700)
    target = folder / "links.json"
    temporary = folder / f".links-{uuid.uuid4().hex}.tmp"
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(state, output, indent=2, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def import_record(thread: JanThread) -> dict[str, Any]:
    return {
        "chat": as_openwebui_chat(thread),
        "meta": {"periscope": {"jan_thread_id": thread.id}},
    }


def linked_imports(data_dir: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for thread_id in state["links"]:
        thread = locate_thread(data_dir, thread_id)
        if not thread.messages:
            continue
        records.append(import_record(thread))
    return records
