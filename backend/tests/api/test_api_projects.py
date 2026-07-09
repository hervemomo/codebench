def test_create_and_list_projects(make_client):
    client, _ = make_client()

    resp = client.post("/api/projects", json={"name": "P1", "context": "ctx"})
    assert resp.status_code == 201
    project = resp.json()
    assert project["name"] == "P1"
    assert project["context"] == "ctx"
    assert project["source_lang"] == "en"
    assert project["target_lang"] == "fr"

    resp = client.get("/api/projects")
    assert resp.status_code == 200
    ids = [p["id"] for p in resp.json()]
    assert project["id"] in ids


def test_list_projects_only_returns_own_org(make_client):
    client_a, _ = make_client()
    client_b, _ = make_client()
    client_a.post("/api/projects", json={"name": "A project"})
    client_b.post("/api/projects", json={"name": "B project"})

    names_a = {p["name"] for p in client_a.get("/api/projects").json()}
    names_b = {p["name"] for p in client_b.get("/api/projects").json()}

    assert "A project" in names_a and "B project" not in names_a
    assert "B project" in names_b and "A project" not in names_b


def test_create_project_missing_name_returns_422(make_client):
    client, _ = make_client()
    resp = client.post("/api/projects", json={"context": "no name field at all"})
    assert resp.status_code == 422


def test_create_project_empty_name_returns_422(make_client):
    client, _ = make_client()
    resp = client.post("/api/projects", json={"name": ""})
    assert resp.status_code == 422


def test_update_context(make_client):
    client, _ = make_client()
    project = client.post("/api/projects", json={"name": "P"}).json()

    resp = client.put(f"/api/projects/{project['id']}/context", json={"context": "new context"})

    assert resp.status_code == 200
    assert resp.json()["context"] == "new context"


def test_update_context_missing_project_returns_404(make_client):
    client, _ = make_client()
    resp = client.put("/api/projects/999999/context", json={"context": "x"})
    assert resp.status_code == 404


def test_create_question(make_client):
    client, _ = make_client()
    project = client.post("/api/projects", json={"name": "P"}).json()

    resp = client.post(f"/api/projects/{project['id']}/questions", json={"text": "Why?", "survey_col": "feedback"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["project_id"] == project["id"]
    assert body["survey_col"] == "feedback"


def test_create_question_validation_error_returns_422(make_client):
    client, _ = make_client()
    project = client.post("/api/projects", json={"name": "P"}).json()

    resp = client.post(f"/api/projects/{project['id']}/questions", json={"text": "Why?"})  # missing survey_col

    assert resp.status_code == 422


def test_create_question_for_missing_project_returns_404(make_client):
    client, _ = make_client()
    resp = client.post("/api/projects/999999/questions", json={"text": "Why?", "survey_col": "feedback"})
    assert resp.status_code == 404
