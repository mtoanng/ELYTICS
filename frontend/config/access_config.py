import os

# Space to required role mapping
ENV = os.getenv("ENVIRONMENT", "dev").lower()

SPACE_ACCESS_MAP = {
    "/sherlock": ["IdM2BCD_holmes_pemely_user"] if ENV == "prod" else ["IdM2BCD_holmes_pemely_development"],
    "/watson": ["IdM2BCD_holmes_pemely_user"] if ENV == "prod" else ["IdM2BCD_holmes_pemely_development"],
    "/mycroft": ["IdM2BCD_holmes_pemely_user"] if ENV == "prod" else ["IdM2BCD_holmes_pemely_development"],
    "/enola": ["IdM2BCD_holmes_pemely_management"] if ENV == "prod" else ["IdM2BCD_holmes_pemely_development"],
}
