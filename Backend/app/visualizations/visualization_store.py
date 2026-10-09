import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from app.database.database_manager import database_manager
from app.visualizations.visualization_service import VisualizationDefinition


STORE_DIR = Path(os.getenv("KENNETH_DATA_DIR") or (Path.home() / ".kenneth"))
STORE_FILE = STORE_DIR / "visualizations.json"
_LOCK = RLock()


class VisualizationPlacement(BaseModel):
    analytics: bool = True
    dashboard: bool = False

    @model_validator(mode="after")
    def at_least_one_destination(self):
        if not self.analytics and not self.dashboard:
            raise ValueError("Selecciona al menos un destino para la visualización.")
        return self


class SavedVisualizationRequest(BaseModel):
    definition: VisualizationDefinition
    placement: VisualizationPlacement = Field(default_factory=VisualizationPlacement)


def _source_key() -> str:
    status = database_manager.status()
    provider = status.get("provider") or "unknown"
    database = status.get("database") or "unknown"
    raw = f"{provider}:{database}".lower()
    return re.sub(r"[^a-z0-9_.:-]+", "_", raw)


def _load() -> dict:
    if not STORE_FILE.exists():
        return {"version": 1, "visualizations": []}
    try:
        return json.loads(STORE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "visualizations": []}


def _write(data: dict) -> None:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    temp = STORE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(STORE_FILE)


def list_saved_visualizations(destination: str | None = None) -> list[dict]:
    source = _source_key()
    with _LOCK:
        items = [item for item in _load()["visualizations"] if item.get("source") == source]
    if destination in {"analytics", "dashboard"}:
        items = [item for item in items if item.get("placement", {}).get(destination)]
    return sorted(items, key=lambda item: item.get("created_at", ""))


def save_visualization(request: SavedVisualizationRequest) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "id": str(uuid4()),
        "source": _source_key(),
        "definition": request.definition.model_dump(),
        "placement": request.placement.model_dump(),
        "created_at": now,
        "updated_at": now,
    }
    with _LOCK:
        data = _load()
        data["visualizations"].append(item)
        _write(data)
    return item


def update_visualization_placement(visualization_id: str, placement: VisualizationPlacement) -> dict:
    source = _source_key()
    with _LOCK:
        data = _load()
        for item in data["visualizations"]:
            if item.get("id") == visualization_id and item.get("source") == source:
                item["placement"] = placement.model_dump()
                item["updated_at"] = datetime.now(timezone.utc).isoformat()
                _write(data)
                return item
    raise ValueError("La visualización no existe para la fuente activa.")


def delete_saved_visualization(visualization_id: str) -> None:
    source = _source_key()
    with _LOCK:
        data = _load()
        before = len(data["visualizations"])
        data["visualizations"] = [
            item for item in data["visualizations"]
            if not (item.get("id") == visualization_id and item.get("source") == source)
        ]
        if len(data["visualizations"]) == before:
            raise ValueError("La visualización no existe para la fuente activa.")
        _write(data)


def update_saved_visualization(visualization_id: str, request: SavedVisualizationRequest) -> dict:
    source = _source_key()
    with _LOCK:
        data = _load()
        for item in data["visualizations"]:
            if item.get("id") == visualization_id and item.get("source") == source:
                item["definition"] = request.definition.model_dump()
                item["placement"] = request.placement.model_dump()
                item["updated_at"] = datetime.now(timezone.utc).isoformat()
                _write(data)
                return item
    raise ValueError("La visualización no existe para la fuente activa.")
