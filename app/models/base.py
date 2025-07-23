from pydantic import BaseModel, Field, ConfigDict
from pydantic.json_schema import JsonSchemaValue
from typing import Optional, Dict, Any, List
from datetime import datetime
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler
    ):
        from pydantic_core import core_schema
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.str_schema(),
            ]),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str):
            if ObjectId.is_valid(v):
                return ObjectId(v)
        raise ValueError("Invalid ObjectId")

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema: JsonSchemaValue, handler) -> JsonSchemaValue:
        field_schema.update(type="string")
        return field_schema


class BaseDocument(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )
    
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    def model_dump(self, **kwargs):
        kwargs.setdefault('by_alias', True)
        return super().model_dump(**kwargs)


class TimestampMixin(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class MetadataMixin(BaseModel):
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ResponseBase(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None
    
    
class PaginatedResponse(ResponseBase):
    page: int = 1
    page_size: int = 20
    total: int = 0
    total_pages: int = 0
    has_next: bool = False
    has_prev: bool = False