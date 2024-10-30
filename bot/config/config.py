from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str


    REF_LINK: str = "https://t.me/PAWSOG_bot/PAWS?startapp=sc9bGaHz"

    AUTO_TASK: bool = True
    IGNORE_TASKS: list[str] = ["wallet"]
    
    DELAY_EACH_ACCOUNT: list[int] = [20, 30]
    ADVANCED_ANTI_DETECTION: bool = True

    USE_PROXY_FROM_FILE: bool = False


settings = Settings()

