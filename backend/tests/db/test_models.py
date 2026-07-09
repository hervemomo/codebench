import pytest
from sqlalchemy.exc import IntegrityError

from app.models import CodeAssignment, CodingRun, Dataset, ExportArtifact, Question, Response
from tests.db.factories import (
    CodeAssignmentFactory,
    CodingRunFactory,
    ExportArtifactFactory,
    OrganizationFactory,
    ProjectFactory,
    ResponseFactory,
    UserFactory,
)


def test_full_object_graph_can_be_created(db_session):
    """Org -> User, Org -> Project -> Question -> Dataset -> Response -> CodeAssignment -> Run -> ExportArtifact."""
    assignment = CodeAssignmentFactory()
    export = ExportArtifactFactory(run=assignment.run)
    db_session.flush()

    assert assignment.id is not None
    assert export.id is not None
    assert assignment.run_id == export.run_id
    assert assignment.response.dataset.question.project.organization.id == assignment.org_id
    # every hop of the graph carries the same tenant
    assert {assignment.org_id, assignment.response.org_id, assignment.response.dataset.org_id,
            assignment.response.dataset.question.org_id, assignment.response.dataset.question.project.org_id,
            assignment.run.org_id, export.org_id} == {assignment.org_id}


def test_cascade_delete_project_removes_question_dataset_and_response(db_session):
    response = ResponseFactory()
    dataset = response.dataset
    question = dataset.question
    project = question.project
    db_session.flush()

    response_id, dataset_id, question_id = response.id, dataset.id, question.id

    db_session.delete(project)
    db_session.flush()

    assert db_session.get(Question, question_id) is None
    assert db_session.get(Dataset, dataset_id) is None
    assert db_session.get(Response, response_id) is None


def test_cascade_delete_run_removes_assignments_and_exports(db_session):
    assignment = CodeAssignmentFactory()
    run = assignment.run
    export = ExportArtifactFactory(run=run)
    db_session.flush()

    assignment_id, export_id = assignment.id, export.id

    db_session.delete(run)
    db_session.flush()

    assert db_session.get(CodeAssignment, assignment_id) is None
    assert db_session.get(ExportArtifact, export_id) is None


def test_parent_run_id_set_null_on_parent_deletion(db_session):
    parent = CodingRunFactory()
    db_session.flush()
    child = CodingRunFactory(question=parent.question, parent_run_id=parent.id)
    db_session.flush()

    child_id = child.id
    db_session.delete(parent)
    db_session.flush()

    refreshed = db_session.get(CodingRun, child_id)
    assert refreshed is not None
    assert refreshed.parent_run_id is None


def test_user_email_unique_constraint(db_session):
    # factory_boy flushes each object as it's created (sqlalchemy_session_persistence
    # = "flush"), so the IntegrityError surfaces from the factory call itself.
    org = OrganizationFactory()
    UserFactory(organization=org, email="dup@example.com")
    db_session.flush()

    with pytest.raises(IntegrityError):
        UserFactory(organization=org, email="dup@example.com")


def test_code_assignment_unique_constraint(db_session):
    assignment = CodeAssignmentFactory(code_id="taste")
    db_session.flush()

    with pytest.raises(IntegrityError):
        CodeAssignmentFactory(response=assignment.response, run=assignment.run, code_id="taste")


def test_org_id_not_nullable(db_session):
    project = ProjectFactory()
    db_session.flush()
    project.org_id = None
    with pytest.raises(IntegrityError):
        db_session.flush()
