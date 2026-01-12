from __future__ import annotations

from typing import Any

from bson import ObjectId
from pydantic import BaseModel


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value: Any) -> ObjectId:
        if isinstance(value, ObjectId):
            return value
        if not ObjectId.is_valid(value):
            raise ValueError("Invalid ObjectId")
        return ObjectId(value)


class CSTBaseModel(BaseModel):
    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
