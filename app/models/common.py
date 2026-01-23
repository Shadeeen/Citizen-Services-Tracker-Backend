# app/models/common.py
from __future__ import annotations

from bson import ObjectId
from pydantic import BaseModel
from pydantic_core import core_schema


def oid_str(x) -> str | None:
    if x is None:
        return None
    if isinstance(x, ObjectId):
        return str(x)
    return str(x)


class PyObjectId(ObjectId):
    """
    Pydantic v2 compatible ObjectId type:
    - Validates strings -> ObjectId
    - Produces proper JSON schema (so /openapi.json works)
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        def validate(v):
            if v is None:
                return None
            if isinstance(v, ObjectId):
                return v
            if isinstance(v, str) and ObjectId.is_valid(v):
                return ObjectId(v)
            raise ValueError("Invalid ObjectId")

        # accept ObjectId or string
        return core_schema.no_info_plain_validator_function(
            validate,
            json_schema_input_schema=core_schema.str_schema()
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema_, handler):
        # This makes OpenAPI show it as a string
        return {"type": "string", "examples": ["64b7c2c9f1c2a8b123456789"]}


class CSTBaseModel(BaseModel):
    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True
