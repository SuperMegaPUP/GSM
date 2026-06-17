from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ObjectionRequest(BaseModel):
    objection_text: str = Field(
        ..., min_length=1, description="Текст возражения клиента"
    )
    context: Optional[str] = Field(
        None, description="Контекст: что предлагаем, ситуация"
    )


class ObjectionVariant(BaseModel):
    style: str = Field(..., description="Стиль ответа: empathic / rational / assertive")
    label: str = Field(..., description="Название варианта")
    text: str = Field(..., description="Текст ответа")


class ObjectionResponse(BaseModel):
    variants: list[ObjectionVariant]


class KnowledgeEntry(BaseModel):
    category: str = Field(..., description="Категория: Цена, Качество, Конкуренты, Сроки")
    objection: str = Field(..., min_length=1, description="Текст возражения")
    core_argument: str = Field(..., min_length=1, description="Ключевой аргумент для отработки")
    successful_reply: str = Field(..., min_length=1, description="Проверенный ответ")


class KnowledgeUploadResponse(BaseModel):
    imported: int
    collection: str
