import sys
from uuid import uuid4

import pytest
from httpx import Headers
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED
from litestar.testing import TestClient

sys.path.append("src/app/")


from app import app

ADMIN_EMAIL = "admin@uni-jena.de"
ADMIN_PASSWORD = "HalloWelt123"
ENGINEER_EMAIL = "malte@uni-jena.de"
MANAGER_EMAIL = "chiara@uni-jena.de"
TEST_PASSWORD = "12345678Hallo"


def unique_text(prefix: str) -> str:
    return f"{prefix} {uuid4().hex}"


def login(
    test_client: TestClient[Litestar],
    email: str = ADMIN_EMAIL,
    password: str = ADMIN_PASSWORD,
) -> Headers:
    data = {
        "email": email,
        "password": password,
    }
    response = test_client.post("/users/login", json=data)
    assert response.status_code == HTTP_201_CREATED
    authorization = response.headers.get("Authorization", None)
    assert authorization is not None
    return Headers({"Authorization": authorization})


def get_admin_header(test_client: TestClient[Litestar]) -> Headers:
    with test_client as client:
        return login(client)


def create_project(
    client: TestClient[Litestar],
    headers: Headers,
    *,
    name: str | None = None,
    managers: list[str] | None = None,
    engineers: list[str] | None = None,
) -> dict:
    response = client.post(
        "/projects",
        json={
            "name": name or unique_text("Test Project"),
            "description": "Temporary integration test project.",
            "managers": managers if managers is not None else [ADMIN_EMAIL],
            "engineers": engineers,
        },
        headers=headers,
    )
    assert response.status_code == HTTP_201_CREATED, response.text
    return response.json()


def register_user(
    client: TestClient[Litestar],
    *,
    email: str | None = None,
    name: str | None = None,
    password: str = TEST_PASSWORD,
) -> dict:
    user_email = email or f"user-{uuid4().hex}@example.com"
    response = client.post(
        "/users/register",
        json={
            "email": user_email,
            "name": name or user_email,
            "password": password,
        },
    )
    assert response.status_code == HTTP_201_CREATED, response.text
    return response.json()


def verify_user(
    client: TestClient[Litestar],
    headers: Headers,
    email: str,
) -> dict:
    response = client.put(f"/users/verify/{email}", headers=headers)
    assert response.status_code == HTTP_200_OK, response.text
    return response.json()


def create_group(
    client: TestClient[Litestar],
    headers: Headers,
    project_id: str,
    *,
    name: str | None = None,
    comment: str | None = None,
) -> dict:
    payload = {"name": name or unique_text("Test Group")}
    if comment is not None:
        payload["comment"] = comment

    response = client.post(
        f"/groups/{project_id}",
        json=payload,
        headers=headers,
    )
    assert response.status_code == HTTP_201_CREATED, response.text
    return response.json()


def create_question(
    client: TestClient[Litestar],
    headers: Headers,
    group_id: str,
    *,
    question: str | None = None,
    comment: str | None = None,
    reference: str | None = None,
    anchor: str | None = None,
    example_answer: str | None = None,
    type: str | None = None,
    sparql_query: str | None = None,
) -> dict:
    payload = {"question": question or unique_text("Test question?")}
    if comment is not None:
        payload["comment"] = comment
    if reference is not None:
        payload["reference"] = reference
    if anchor is not None:
        payload["anchor"] = anchor
    if example_answer is not None:
        payload["exampleAnswer"] = example_answer
    if type is not None:
        payload["type"] = type
    if sparql_query is not None:
        payload["sparqlQuery"] = sparql_query

    response = client.post(f"/questions/by_group/{group_id}", json=payload, headers=headers)
    assert response.status_code == HTTP_201_CREATED, response.text
    return response.json()


def create_consolidation(
    client: TestClient[Litestar],
    headers: Headers,
    project_id: str,
    *,
    question_ids: list[str],
    target_question: dict | None = None,
    target_question_id: str | None = None,
) -> dict:
    payload: dict = {"sourceQuestionIds": question_ids}
    if target_question_id is not None:
        payload["targetQuestion"] = {"id": target_question_id}
    else:
        payload["targetQuestion"] = target_question or {"question": unique_text("Target question?")}

    response = client.post(f"/consolidations/{project_id}", json=payload, headers=headers)
    assert response.status_code == HTTP_201_CREATED, response.text
    return response.json()


def create_project_group(
    client: TestClient[Litestar],
    headers: Headers,
    *,
    managers: list[str] | None = None,
    engineers: list[str] | None = None,
) -> tuple[dict, dict]:
    project = create_project(
        client,
        headers,
        managers=managers,
        engineers=engineers,
    )
    group = create_group(client, headers, project["id"])
    return project, group


@pytest.fixture(scope="module")
def admin_header() -> Headers:
    return get_admin_header(TestClient(app=app))  # type: ignore


@pytest.fixture(scope="module")
def test_client() -> TestClient[Litestar]:
    return TestClient(app=app)  # type: ignore
