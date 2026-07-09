"""factory-boy factories for the db test suite.

`sqlalchemy_session` is bound per-test by the `_bind_factories` autouse
fixture in conftest.py — do not set it here.
"""

from __future__ import annotations

import factory
from factory.alchemy import SQLAlchemyModelFactory

from app.models import CodeAssignment, CodingRun, CodingRunKind, CodingRunStatus, Dataset, ExportArtifact, Organization, Project, Question, Response, User, UserRole


class BaseFactory(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session_persistence = "flush"


class OrganizationFactory(BaseFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Org {n}")


class UserFactory(BaseFactory):
    class Meta:
        model = User

    organization = factory.SubFactory(OrganizationFactory)
    org_id = factory.LazyAttribute(lambda o: o.organization.id)
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password_hash = "not-a-real-hash"
    role = UserRole.ANALYST


class ProjectFactory(BaseFactory):
    class Meta:
        model = Project

    organization = factory.SubFactory(OrganizationFactory)
    org_id = factory.LazyAttribute(lambda o: o.organization.id)
    name = factory.Sequence(lambda n: f"Project {n}")
    context = "test survey context"
    source_lang = "en"
    target_lang = "fr"
    codebook_lang = "fr"


class QuestionFactory(BaseFactory):
    class Meta:
        model = Question

    project = factory.SubFactory(ProjectFactory)
    org_id = factory.LazyAttribute(lambda o: o.project.org_id)
    project_id = factory.LazyAttribute(lambda o: o.project.id)
    text = "What do you think of this product?"
    survey_col = "feedback"


class DatasetFactory(BaseFactory):
    class Meta:
        model = Dataset

    question = factory.SubFactory(QuestionFactory)
    org_id = factory.LazyAttribute(lambda o: o.question.org_id)
    question_id = factory.LazyAttribute(lambda o: o.question.id)
    file_key = factory.Sequence(lambda n: f"datasets/file-{n}.xlsx")
    sheet = "0"
    status = "uploaded"


class ResponseFactory(BaseFactory):
    class Meta:
        model = Response

    dataset = factory.SubFactory(DatasetFactory)
    org_id = factory.LazyAttribute(lambda o: o.dataset.org_id)
    dataset_id = factory.LazyAttribute(lambda o: o.dataset.id)
    raw_text = "raw response text"
    clean_text = "clean response text"
    translated_text = "translated response text"
    is_valid = True
    invalid_reason = None


class CodingRunFactory(BaseFactory):
    class Meta:
        model = CodingRun

    question = factory.SubFactory(QuestionFactory)
    org_id = factory.LazyAttribute(lambda o: o.question.org_id)
    question_id = factory.LazyAttribute(lambda o: o.question.id)
    parent_run_id = None
    kind = CodingRunKind.S2
    status = CodingRunStatus.DRAFT
    config_json = factory.LazyFunction(dict)
    codebook_json = factory.LazyFunction(dict)
    token_usage = factory.LazyFunction(dict)


class CodeAssignmentFactory(BaseFactory):
    class Meta:
        model = CodeAssignment

    response = factory.SubFactory(ResponseFactory)
    # Defaults to a run on the *same* question/org as `response`, not an
    # independent chain — a CodeAssignment's response and run always belong
    # to one tenant in practice, and several tests assert that consistency.
    run = factory.LazyAttribute(
        lambda o: CodingRunFactory(question=o.response.dataset.question, org_id=o.response.org_id)
    )
    org_id = factory.LazyAttribute(lambda o: o.response.org_id)
    response_id = factory.LazyAttribute(lambda o: o.response.id)
    run_id = factory.LazyAttribute(lambda o: o.run.id)
    code_id = "code_taste"
    confidence = 0.9
    reasoning = None


class ExportArtifactFactory(BaseFactory):
    class Meta:
        model = ExportArtifact

    run = factory.SubFactory(CodingRunFactory)
    org_id = factory.LazyAttribute(lambda o: o.run.org_id)
    run_id = factory.LazyAttribute(lambda o: o.run.id)
    kind = "xlsx"
    file_key = factory.Sequence(lambda n: f"exports/report-{n}.xlsx")


ALL_FACTORIES = [
    OrganizationFactory,
    UserFactory,
    ProjectFactory,
    QuestionFactory,
    DatasetFactory,
    ResponseFactory,
    CodingRunFactory,
    CodeAssignmentFactory,
    ExportArtifactFactory,
]
