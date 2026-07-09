"""User from org A requests org B's project/dataset IDs directly -> 404, never
403 (don't leak existence). Uploaded files from org B stay unreachable via
org A because the dataset lookup itself 404s before the file is ever touched.
"""


def _create_project(client) -> dict:
    return client.post("/api/projects", json={"name": "Org project", "target_lang": "en"}).json()


def _create_question(client, project_id: int) -> dict:
    return client.post(f"/api/projects/{project_id}/questions", json={"text": "Q?", "survey_col": "feedback"}).json()


def _upload_dataset(client, question_id: int, tiny_survey_bytes: bytes) -> dict:
    resp = client.post(
        f"/api/questions/{question_id}/datasets",
        files={"file": ("tiny_survey.xlsx", tiny_survey_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_cross_org_project_context_update_returns_404(make_client):
    client_a, _ = make_client()
    client_b, _ = make_client()
    project_b = _create_project(client_b)

    resp = client_a.put(f"/api/projects/{project_b['id']}/context", json={"context": "hacked"})

    assert resp.status_code == 404


def test_cross_org_question_creation_on_foreign_project_returns_404(make_client):
    client_a, _ = make_client()
    client_b, _ = make_client()
    project_b = _create_project(client_b)

    resp = client_a.post(f"/api/projects/{project_b['id']}/questions", json={"text": "Q", "survey_col": "feedback"})

    assert resp.status_code == 404


def test_cross_org_dataset_upload_on_foreign_question_returns_404(make_client, tiny_survey_bytes):
    client_a, _ = make_client()
    client_b, _ = make_client()
    project_b = _create_project(client_b)
    question_b = _create_question(client_b, project_b["id"])

    resp = client_a.post(
        f"/api/questions/{question_b['id']}/datasets",
        files={"file": ("tiny_survey.xlsx", tiny_survey_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 404


def test_cross_org_dataset_stats_and_preprocess_return_404(make_client, tiny_survey_bytes):
    client_a, _ = make_client()
    client_b, _ = make_client()
    project_b = _create_project(client_b)
    question_b = _create_question(client_b, project_b["id"])
    dataset_b = _upload_dataset(client_b, question_b["id"], tiny_survey_bytes)

    assert client_a.get(f"/api/datasets/{dataset_b['id']}/stats").status_code == 404
    assert client_a.post(f"/api/datasets/{dataset_b['id']}/preprocess").status_code == 404

    # org B itself can reach it fine — proves the 404 above is org-scoping, not a broken route
    assert client_b.get(f"/api/datasets/{dataset_b['id']}/stats").status_code == 200


def test_cross_org_uploaded_file_unreachable_via_org_a(make_client, tiny_survey_bytes):
    """The file genuinely exists in MinIO (org B can read it back directly),
    but org A can never even learn its file_key — the dataset lookup that
    would expose it already 404s for org A's session."""
    client_a, _ = make_client()
    client_b, _ = make_client()
    project_b = _create_project(client_b)
    question_b = _create_question(client_b, project_b["id"])
    dataset_b = _upload_dataset(client_b, question_b["id"], tiny_survey_bytes)

    from app import storage
    assert storage.get_object(dataset_b["file_key"]) == tiny_survey_bytes  # file really is there

    # Org A has no endpoint that can ever surface org B's file_key.
    assert client_a.get(f"/api/datasets/{dataset_b['id']}/stats").status_code == 404
    assert client_a.post(f"/api/datasets/{dataset_b['id']}/preprocess").status_code == 404
