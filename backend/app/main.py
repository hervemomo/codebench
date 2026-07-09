from fastapi import FastAPI

from app.config import get_settings
from app.routers import auth, datasets, jobs, projects

app = FastAPI(title="CodeBench API")

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(datasets.router)
app.include_router(jobs.router)


@app.get("/healthz")
def healthz():
    settings = get_settings()
    return {"status": "ok", "version": settings.app_version}
