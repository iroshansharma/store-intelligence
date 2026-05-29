import os

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./store_intelligence.db")
    QUEUE_DEPTH_THRESHOLD: int = int(os.getenv("QUEUE_DEPTH_THRESHOLD", "5"))
    BASE_CONVERSION_RATE: float = float(os.getenv("BASE_CONVERSION_RATE", "0.15"))
    STALE_FEED_THRESHOLD_SECONDS: int = int(os.getenv("STALE_FEED_THRESHOLD_SECONDS", "600"))  # 10 minutes
    DEAD_ZONE_THRESHOLD_SECONDS: int = int(os.getenv("DEAD_ZONE_THRESHOLD_SECONDS", "1800"))  # 30 minutes
    VERSION: str = "1.0.0"

settings = Settings()
