from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    email: str
    phone: str
    is_active: bool

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str = ""
    role: str = "staff"
    email: str = ""
    phone: str = ""


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    is_active: bool | None = None
    password: str | None = None
