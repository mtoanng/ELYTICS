import os

# Space to required role mapping
ENV = os.getenv("ENVIRONMENT", "dev").lower()

SPACE_ACCESS_MAP = {
    "/elytics": ["IdM2BCD_holmes_pemely_sherlock"] if ENV == "prod" else ["IdM2BCD_holmes_pemely_development"],
}
