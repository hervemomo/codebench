from fastapi import FastAPI

from app.config import get_settings

app = FastAPI(title="CodeBench API")


@app.get("/healthz")
def healthz():
    settings = get_settings()
    return {"status": "ok", "version": settings.app_version}
