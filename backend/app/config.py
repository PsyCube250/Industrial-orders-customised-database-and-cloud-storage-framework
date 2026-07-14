from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./prodflow.db"
    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12
    upload_dir: str = "./uploads"

    class Config:
        env_file = ".env"


settings = Settings()
