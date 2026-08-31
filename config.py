from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    users_url: str
    posts_url: str

    class Config:
        env_file = ".env"

settings = Settings()