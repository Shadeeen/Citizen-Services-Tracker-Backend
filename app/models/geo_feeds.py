from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from pydantic import Field

from app.models.common import CSTBaseModel, PyObjectId


class GeoJSON(CSTBaseModel):
    type: str = Field("FeatureCollection", regex="^FeatureCollection$")
    features: List[Dict[str, Any]] = Field(default_factory=list)


class Aggregation(CSTBaseModel):
    method: str
    weight_formula: str
    tile_hint: str


class GeoFeed(CSTBaseModel):
    id: PyObjectId | None = Field(None, alias="_id")
    feed_name: str
    generated_at: datetime
    filters: Dict[str, Any] = Field(default_factory=dict)
    geojson: GeoJSON
    aggregation: Aggregation
