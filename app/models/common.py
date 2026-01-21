from __future__ import annotations

from typing import Any

from bson import ObjectId
from pydantic import BaseModel
from pydantic import BaseModel


from bson import ObjectId
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type,
        handler: GetCoreSchemaHandler,
    ):
        return core_schema.no_info_plain_validator_function(cls.validate)

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")


class CSTBaseModel(BaseModel):
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }
