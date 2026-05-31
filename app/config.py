from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    HOSPITAL_API_BASE_URL: str = "https://hospital-directory.onrender.com"
    MAX_CSV_SIZE: int = 20

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
