from app import storage


def _make_question(client) -> dict:
    project = client.post("/api/projects", json={"name": "P"}).json()
    return client.post(f"/api/projects/{project['id']}/questions", json={"text": "Q", "survey_col": "feedback"}).json()


def test_upload_dataset_returns_201_with_preview_and_columns(make_client, tiny_survey_bytes):
    client, _ = make_client()
    question = _make_question(client)

    resp = client.post(
        f"/api/questions/{question['id']}/datasets",
        files={"file": ("tiny_survey.xlsx", tiny_survey_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "uploaded"
    assert "feedback" in body["columns"]
    assert len(body["preview"]) == 10
    assert all("feedback" in row for row in body["preview"])


def test_uploaded_file_exists_in_minio(make_client, tiny_survey_bytes):
    client, _ = make_client()
    question = _make_question(client)

    body = client.post(
        f"/api/questions/{question['id']}/datasets",
        files={"file": ("tiny_survey.xlsx", tiny_survey_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    ).json()

    fetched = storage.get_object(body["file_key"])
    assert fetched == tiny_survey_bytes


def test_upload_unsupported_file_type_returns_422(make_client):
    client, _ = make_client()
    question = _make_question(client)

    resp = client.post(
        f"/api/questions/{question['id']}/datasets",
        files={"file": ("notes.txt", b"just some text", "text/plain")},
    )

    assert resp.status_code == 422


def test_upload_to_missing_question_returns_404(make_client, tiny_survey_bytes):
    client, _ = make_client()
    resp = client.post(
        "/api/questions/999999/datasets",
        files={"file": ("tiny_survey.xlsx", tiny_survey_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert resp.status_code == 404
