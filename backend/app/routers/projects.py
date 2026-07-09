"""POST/GET /api/projects, POST /api/projects/{id}/questions, PUT /api/projects/{id}/context.

Every route depends on get_current_user; every query goes through
scoped_query so cross-org IDs 404 (never 403 — don't leak existence).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.db.base import get_db_session
from app.db.scoped import scoped_query
from app.models import Project, Question

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    context: str = ""
    source_lang: str = Field(default="en", min_length=2, max_length=8)
    target_lang: str = Field(default="fr", min_length=2, max_length=8)
    codebook_lang: str = Field(default="fr", min_length=2, max_length=8)


class ProjectContextUpdate(BaseModel):
    context: str


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    context: str
    source_lang: str
    target_lang: str
    codebook_lang: str


class QuestionCreate(BaseModel):
    text: str = Field(min_length=1)
    survey_col: str = Field(min_length=1, max_length=255)


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    text: str
    survey_col: str


def get_project_or_404(session: Session, org_id: int, project_id: int) -> Project:
    project = session.scalars(
        scoped_query(session, Project, org_id).where(Project.id == project_id)
    ).one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate, current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session)
):
    project = Project(org_id=current.org_id, **payload.model_dump())
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session)):
    return list(session.scalars(scoped_query(session, Project, current.org_id)).all())


@router.put("/{project_id}/context", response_model=ProjectOut)
def update_context(
    project_id: int, payload: ProjectContextUpdate,
    current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session),
):
    project = get_project_or_404(session, current.org_id, project_id)
    project.context = payload.context
    session.commit()
    session.refresh(project)
    return project


@router.post("/{project_id}/questions", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
def create_question(
    project_id: int, payload: QuestionCreate,
    current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session),
):
    project = get_project_or_404(session, current.org_id, project_id)
    question = Question(org_id=current.org_id, project_id=project.id, **payload.model_dump())
    session.add(question)
    session.commit()
    session.refresh(question)
    return question
