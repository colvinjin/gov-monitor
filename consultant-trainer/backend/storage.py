"""
训练记录存储
先使用本地 JSON 文件，后续可平滑迁移到 SQLite / 数据库
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
INDEX_FILE = DATA_DIR / "sessions_index.json"


class TrainingStorage:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        if not INDEX_FILE.exists():
            INDEX_FILE.write_text("[]", encoding="utf-8")

    def save_session(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(payload)
        record_id = record.get("record_id") or str(uuid.uuid4())
        record["record_id"] = record_id
        record.setdefault("saved_at", datetime.now().isoformat())

        session_path = SESSIONS_DIR / f"{record_id}.json"
        session_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        index = self._load_index()
        summary = {
            "record_id": record_id,
            "saved_at": record["saved_at"],
            "session_id": record.get("session_id"),
            "parent_type": record.get("parent_type"),
            "parent_type_name": record.get("parent_type_name"),
            "scenario": record.get("scenario"),
            "scenario_name": record.get("scenario_name"),
            "turns": record.get("turns", 0),
            "overall_score": record.get("evaluation", {}).get("overall_score", 0),
            "level": record.get("evaluation", {}).get("level", "未知")
        }

        index = [item for item in index if item.get("record_id") != record_id]
        index.insert(0, summary)
        INDEX_FILE.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return summary

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._load_index()[:limit]

    def get_session(self, record_id: str) -> Optional[Dict[str, Any]]:
        session_path = SESSIONS_DIR / f"{record_id}.json"
        if not session_path.exists():
            return None
        return json.loads(session_path.read_text(encoding="utf-8"))

    def _load_index(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []


storage = TrainingStorage()
