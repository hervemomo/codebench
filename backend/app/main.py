from fastapi import FastAPI

from app.config import get_settings
from app.routers import auth, coding, datasets, jobs, projects, refine, results

app = FastAPI(title="CodeBench API")

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(datasets.router)
app.include_router(coding.router)
app.include_router(refine.router)
app.include_router(results.router)
app.include_router(jobs.router)


@app.get("/healthz")
def healthz():
    settings = get_settings()
    return {"status": "ok", "version": settings.app_version}
