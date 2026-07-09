"""Two orgs; org A must never be able to read org B's rows at any depth of
the object graph, and no tenant row can be inserted without an org_id.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.scoped import scoped_query
from app.models import CodeAssignment, Dataset, Project, Question, Response, User
from tests.db.factories import (
    CodeAssignmentFactory,
    CodingRunFactory,
    DatasetFactory,
    OrganizationFactory,
    ProjectFactory,
    QuestionFactory,
    ResponseFactory,
    UserFactory,
)


def _build_full_graph(org):
    """Project -> Question -> Dataset -> Response -> CodeAssignment (+ its run), all under `org`."""
    project = ProjectFactory(organization=org)
    question = QuestionFactory(project=project, org_id=org.id)
    dataset = DatasetFactory(question=question, org_id=org.id)
    response = ResponseFactory(dataset=dataset, org_id=org.id)
    run = CodingRunFactory(question=question, org_id=org.id)
    return CodeAssignmentFactory(response=response, run=run, org_id=org.id)


@pytest.fixture()
def two_orgs(db_session):
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    db_session.flush()

    assignment_a = _build_full_graph(org_a)
    assignment_b = _build_full_graph(org_b)
    user_a = UserFactory(organization=org_a)
    user_b = UserFactory(organization=org_b)
    db_session.flush()

    return {
        "org_a": org_a, "org_b": org_b,
        "assignment_a": assignment_a, "assignment_b": assignment_b,
        "user_a": user_a, "user_b": user_b,
    }


@pytest.mark.parametrize("model", [Project, Question, Dataset, Response, CodeAssignment, User])
def test_scoped_query_never_returns_other_org_rows(db_session, two_orgs, model):
    org_a_id = two_orgs["org_a"].id

    rows = db_session.scalars(scoped_query(db_session, model, org_a_id)).all()

    assert len(rows) >= 1
    assert all(row.org_id == org_a_id for row in rows)


def test_scoped_query_project_isolation_end_to_end(db_session, two_orgs):
    org_a_id = two_orgs["org_a"].id

    projects_a = db_session.scalars(scoped_query(db_session, Project, org_a_id)).all()
    ids_a = {p.id for p in projects_a}

    project_a_id = two_orgs["assignment_a"].response.dataset.question.project_id
    project_b_id = two_orgs["assignment_b"].response.dataset.question.project_id
    assert project_a_id in ids_a
    assert project_b_id not in ids_a


def test_scoped_query_response_isolation(db_session, two_orgs):
    org_a_id = two_orgs["org_a"].id

    responses = db_session.scalars(scoped_query(db_session, Response, org_a_id)).all()
    response_ids = {r.id for r in responses}

    assert two_orgs["assignment_a"].response_id in response_ids
    assert two_orgs["assignment_b"].response_id not in response_ids


def test_scoped_query_assignment_isolation(db_session, two_orgs):
    org_a_id = two_orgs["org_a"].id

    assignments = db_session.scalars(scoped_query(db_session, CodeAssignment, org_a_id)).all()
    assignment_ids = {a.id for a in assignments}

    assert two_orgs["assignment_a"].id in assignment_ids
    assert two_orgs["assignment_b"].id not in assignment_ids


def test_inserting_tenant_row_without_org_id_raises_integrity_error(db_session):
    project = ProjectFactory()
    db_session.flush()
    project.org_id = None

    with pytest.raises(IntegrityError):
        db_session.flush()
