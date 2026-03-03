from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from internal.poller import start_scheduler
from internal.auth import verify_oidc_token
from routers.sherlock.tables import router as tables_router

load_dotenv()

app = FastAPI()

app.include_router(tables_router)

start_scheduler()

if os.environ.get("ENVIRONMENT") == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.get("/api/groups")
def get_user_groups(token: dict = Depends(verify_oidc_token)):
    user_groups = token.get("groups", [])
    holmes_groups = [g for g in user_groups if g.startswith("IdM2BCD_holmes_pemely_")]
    return {
        "user": token.get("email"),
        "holmes_groups": holmes_groups,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)