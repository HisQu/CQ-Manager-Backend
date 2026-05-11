from httpx import Headers
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED
from litestar.testing import TestClient

from ._fixtures import (
    ENGINEER_EMAIL,
    MANAGER_EMAIL,
    admin_header,
    create_group,
    create_project,
    create_question,
    login,
    test_client,
    unique_text,
)


def create_topic(
    client: TestClient[Litestar],
    headers: Headers,
    project_id: str,
    *,
    name: str | None = None,
    identifier: str | None = None,
) -> dict:
    payload = {"name": name or unique_text("Topic")}
    if identifier is not None:
        payload["identifier"] = identifier

    response = client.post(f"/topics/{project_id}", json=payload, headers=headers)
    assert response.status_code == HTTP_201_CREATED, response.text
    return response.json()


def test_topic_identifier_generation_fills_first_gap(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header, engineers=[ENGINEER_EMAIL])
        engineer_header = login(client, ENGINEER_EMAIL)

        try:
            create_topic(client, engineer_header, project["id"], identifier="A")
            create_topic(client, engineer_header, project["id"], identifier="B")
            create_topic(client, engineer_header, project["id"], identifier="C")
            create_topic(client, engineer_header, project["id"], identifier="F")

            auto_topic = create_topic(client, engineer_header, project["id"])
            assert auto_topic["identifier"] == "D"

            topics_response = client.get(f"/topics/{project['id']}", headers=engineer_header)
            assert topics_response.status_code == HTTP_200_OK, topics_response.text
            assert [topic["identifier"] for topic in topics_response.json()] == ["A", "B", "C", "D", "F"]
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_topic_identifier_validation_and_immutability(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header, engineers=[ENGINEER_EMAIL])
        engineer_header = login(client, ENGINEER_EMAIL)

        try:
            topic = create_topic(client, engineer_header, project["id"], identifier="A")

            duplicate_response = client.post(
                f"/topics/{project['id']}",
                json={"name": unique_text("Duplicate Topic"), "identifier": "A"},
                headers=engineer_header,
            )
            assert duplicate_response.status_code == HTTP_400_BAD_REQUEST, duplicate_response.text

            update_response = client.put(
                f"/topics/{project['id']}/{topic['id']}",
                json={"name": "Updated topic", "identifier": "B"},
                headers=engineer_header,
            )
            assert update_response.status_code == HTTP_400_BAD_REQUEST, update_response.text
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_topic_management_requires_project_engineer(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header, managers=[MANAGER_EMAIL], engineers=[ENGINEER_EMAIL])
        manager_header = login(client, MANAGER_EMAIL)

        try:
            response = client.post(
                f"/topics/{project['id']}",
                json={"name": unique_text("Blocked Topic")},
                headers=manager_header,
            )
            assert response.status_code == HTTP_401_UNAUTHORIZED, response.text
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_question_topic_assignment_change_and_remove(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header, engineers=[ENGINEER_EMAIL])
        group = create_group(client, admin_header, project["id"])
        question = create_question(client, admin_header, group["id"], type="SCQ")
        engineer_header = login(client, ENGINEER_EMAIL)

        try:
            topic_a = create_topic(client, engineer_header, project["id"], identifier="A")
            topic_b = create_topic(client, engineer_header, project["id"], identifier="B")

            assign_response = client.post(
                f"/topics/{project['id']}/{topic_a['id']}/questions/{question['id']}",
                headers=engineer_header,
            )
            assert assign_response.status_code == HTTP_200_OK, assign_response.text
            assigned = assign_response.json()
            assert assigned["topic"]["identifier"] == "A"
            assert assigned["type"] == "SCQ"

            duplicate_assign_response = client.post(
                f"/topics/{project['id']}/{topic_b['id']}/questions/{question['id']}",
                headers=engineer_header,
            )
            assert duplicate_assign_response.status_code == HTTP_400_BAD_REQUEST, duplicate_assign_response.text

            change_response = client.put(
                f"/topics/{project['id']}/{topic_b['id']}/questions/{question['id']}",
                headers=engineer_header,
            )
            assert change_response.status_code == HTTP_200_OK, change_response.text
            assert change_response.json()["topic"]["identifier"] == "B"

            remove_response = client.delete(
                f"/topics/{project['id']}/questions/{question['id']}",
                headers=engineer_header,
            )
            assert remove_response.status_code == HTTP_200_OK, remove_response.text
            assert remove_response.json()["topic"] is None
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
