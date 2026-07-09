"""SQLAlchemy models. Import this module to register all tables on Base.metadata."""

from app.db.base import Base
from app.models.code_assignment import CodeAssignment
from app.models.coding_run import CodingRun
from app.models.dataset import Dataset
from app.models.enums import CodingRunKind, UserRole
from app.models.export_artifact import ExportArtifact
from app.models.organization import Organization
from app.models.project import Project
from app.models.question import Question
from app.models.response import Response
from app.models.user import User

__all__ = [
    "Base",
    "Organization",
    "User",
    "UserRole",
    "Project",
    "Question",
    "Dataset",
    "Response",
    "CodingRun",
    "CodingRunKind",
    "CodeAssignment",
    "ExportArtifact",
]

TENANT_MODELS = [User, Project, Question, Dataset, Response, CodingRun, CodeAssignment, ExportArtifact]
