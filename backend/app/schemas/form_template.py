from typing import Optional
from pydantic import BaseModel


class FormTemplateSummary(BaseModel):
    id: str
    name: str
    institution: str
    version: str
    supported_languages: list[str]

    model_config = {"from_attributes": True}


class FormTemplateRead(BaseModel):
    id: str
    name: str
    institution: str
    version: str
    supported_languages: list[str]

    model_config = {"from_attributes": True}
