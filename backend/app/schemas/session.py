from pydantic import BaseModel


class SessionCreate(BaseModel):
    preferred_language: str = "en"


class SessionRead(BaseModel):
    session_token: str
    user_id: str
    preferred_language: str

    model_config = {"from_attributes": True}
