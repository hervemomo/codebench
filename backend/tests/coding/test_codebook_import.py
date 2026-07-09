"""kind="import": load_user_codebook from list/json/csv/xlsx sources, each
code marked "proposed" (same review gate as AI-generated codes) and assigned
a code_id even when the source didn't provide one."""

import base64
import io
import json

import pandas as pd


def test_import_from_list_format(seed_dataset):
    seeded = seed_dataset(["placeholder response " + str(i) for i in range(10)])
    client = seeded["client"]

    resp = client.post(f"/api/questions/{seeded['question_id']}/runs", json={
        "kind": "import",
        "codebook_source": [{"name": "Taste & Flavor", "definition": "Mentions of taste."}, "Price & Value"],
    })
    assert resp.status_code == 202, resp.text
    run = client.get(f"/api/runs/{resp.json()['id']}").json()
    codes = run["codebook"]["codes"]
    assert {c["name"] for c in codes} == {"Taste & Flavor", "Price & Value"}
    assert all(c["status"] == "proposed" for c in codes)


def test_import_from_json_format_with_missing_ids_auto_generates_code_id(seed_dataset):
    seeded = seed_dataset(["placeholder response " + str(i) for i in range(10)])
    client = seeded["client"]

    payload = [
        {"name": "Availability", "definition": "In stock nearby."},
        {"name": "Packaging & Design"},
    ]
    content_b64 = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")

    resp = client.post(f"/api/questions/{seeded['question_id']}/runs", json={
        "kind": "import",
        "codebook_source": {"format": "json", "content_base64": content_b64},
    })
    assert resp.status_code == 202, resp.text
    codes = client.get(f"/api/runs/{resp.json()['id']}").json()["codebook"]["codes"]
    assert len(codes) == 2
    assert all(c["code_id"] for c in codes)
    assert len({c["code_id"] for c in codes}) == 2  # unique


def test_import_from_csv_format_with_custom_columns(seed_dataset):
    seeded = seed_dataset(["placeholder response " + str(i) for i in range(10)])
    client = seeded["client"]

    csv_text = "code_name,code_definition\nEnergy & Health,Feeling energized.\nOther,Catch-all.\n"
    content_b64 = base64.b64encode(csv_text.encode("utf-8")).decode("ascii")

    resp = client.post(f"/api/questions/{seeded['question_id']}/runs", json={
        "kind": "import",
        "codebook_source": {
            "format": "csv", "content_base64": content_b64,
            "name_column": "code_name", "definition_column": "code_definition",
        },
    })
    assert resp.status_code == 202, resp.text
    codes = client.get(f"/api/runs/{resp.json()['id']}").json()["codebook"]["codes"]
    assert {c["name"] for c in codes} == {"Energy & Health", "Other"}
    assert next(c for c in codes if c["name"] == "Energy & Health")["definition"] == "Feeling energized."


def test_import_from_xlsx_format(seed_dataset):
    seeded = seed_dataset(["placeholder response " + str(i) for i in range(10)])
    client = seeded["client"]

    df = pd.DataFrame({"name": ["Brand Loyalty", "Social Occasion"], "definition": ["Trusts the brand.", "Parties and gatherings."]})
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    content_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    resp = client.post(f"/api/questions/{seeded['question_id']}/runs", json={
        "kind": "import",
        "codebook_source": {"format": "xlsx", "content_base64": content_b64},
    })
    assert resp.status_code == 202, resp.text
    codes = client.get(f"/api/runs/{resp.json()['id']}").json()["codebook"]["codes"]
    assert {c["name"] for c in codes} == {"Brand Loyalty", "Social Occasion"}


def test_import_does_not_auto_inject_catch_all_at_creation(seed_dataset):
    seeded = seed_dataset(["placeholder response " + str(i) for i in range(10)])
    client = seeded["client"]

    resp = client.post(f"/api/questions/{seeded['question_id']}/runs", json={
        "kind": "import", "codebook_source": ["Taste & Flavor"],
    })
    codes = client.get(f"/api/runs/{resp.json()['id']}").json()["codebook"]["codes"]
    assert len(codes) == 1
    assert codes[0]["name"] == "Taste & Flavor"


def test_import_without_codebook_source_returns_422(seed_dataset):
    seeded = seed_dataset(["placeholder response " + str(i) for i in range(10)])
    client = seeded["client"]

    resp = client.post(f"/api/questions/{seeded['question_id']}/runs", json={"kind": "import"})
    assert resp.status_code == 422
