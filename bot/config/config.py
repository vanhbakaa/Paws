from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str


    REF_LINK: str = ""

    AUTO_TASK: bool = True
    AUTO_CONNECT_WALLET: bool = True
    AUTO_DISCONNECT_WALLET: bool = False

    DELAY_EACH_ACCOUNT: list[int] = [20, 30]
    IGNORE_TASKS: list[str] = ["boost", "vote", "voteup", "votedown", "mystery"]
    DISABLE_JOIN_CHANNEL_TASKS: bool = True
    ADVANCED_ANTI_DETECTION: bool = False

    USE_PROXY_FROM_FILE: bool = False


settings = Settings()

