from httpx import Headers
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED
from litestar.testing import TestClient

from ._fixtures import (
    ENGINEER_EMAIL,
    MANAGER_EMAIL,
    admin_header,
    create_consolidation,
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
        admin_header = login(client)
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
        admin_header = login(client)
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
        admin_header = login(client)
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
        admin_header = login(client)
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
            assert "topicId" not in assigned
            assert set(assigned["topic"]) == {"id", "identifier", "name"}
            assert assigned["topic"]["identifier"] == "A"
            assert assigned["cqCatalogueIdentifier"] == "A.1"
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
            changed = change_response.json()
            assert "topicId" not in changed
            assert set(changed["topic"]) == {"id", "identifier", "name"}
            assert changed["topic"]["identifier"] == "B"
            assert changed["cqCatalogueIdentifier"] == "B.1"

            detail_response = client.get(
                f"/questions/{question['id']}",
                headers=admin_header,
            )
            assert detail_response.status_code == HTTP_200_OK, detail_response.text
            detail = detail_response.json()
            assert "topicId" not in detail
            assert set(detail["topic"]) == {"id", "identifier", "name"}
            assert detail["topic"]["identifier"] == "B"
            assert detail["topic"]["name"] == topic_b["name"]
            assert detail["cqCatalogueIdentifier"] == "B.1"

            resolve_response = client.get(
                f"/questions/by_project/{project['id']}/catalogue/B.1",
                headers=admin_header,
            )
            assert resolve_response.status_code == HTTP_200_OK, resolve_response.text
            assert resolve_response.json() == {
                "id": question["id"],
                "groupId": group["id"],
                "cqCatalogueIdentifier": "B.1",
            }

            list_response = client.get(
                f"/questions/by_group/{group['id']}",
                headers=admin_header,
            )
            assert list_response.status_code == HTTP_200_OK, list_response.text
            listed_question = next(item for item in list_response.json() if item["id"] == question["id"])
            assert "topicId" not in listed_question
            assert set(listed_question["topic"]) == {"id", "identifier", "name"}
            assert listed_question["topic"]["identifier"] == "B"
            assert listed_question["cqCatalogueIdentifier"] == "B.1"

            remove_response = client.delete(
                f"/topics/{project['id']}/questions/{question['id']}",
                headers=engineer_header,
            )
            assert remove_response.status_code == HTTP_200_OK, remove_response.text
            removed = remove_response.json()
            assert "topicId" not in removed
            assert removed["topic"] is None
            assert removed["cqCatalogueIdentifier"] is None
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_cq_catalogue_identifier_uses_topic_not_group(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        admin_header = login(client)
        project = create_project(client, admin_header, engineers=[ENGINEER_EMAIL])
        group = create_group(client, admin_header, project["id"])
        first_question = create_question(client, admin_header, group["id"])
        second_question = create_question(client, admin_header, group["id"])
        engineer_header = login(client, ENGINEER_EMAIL)

        try:
            topic_a = create_topic(client, engineer_header, project["id"], identifier="A")

            first_assign = client.post(
                f"/topics/{project['id']}/{topic_a['id']}/questions/{first_question['id']}",
                headers=engineer_header,
            )
            assert first_assign.status_code == HTTP_200_OK, first_assign.text
            assert first_assign.json()["cqCatalogueIdentifier"] == "A.1"

            second_assign = client.post(
                f"/topics/{project['id']}/{topic_a['id']}/questions/{second_question['id']}",
                headers=engineer_header,
            )
            assert second_assign.status_code == HTTP_200_OK, second_assign.text
            assert second_assign.json()["cqCatalogueIdentifier"] == "A.2"

            second_resolve = client.get(
                f"/questions/by_project/{project['id']}/catalogue/a.2",
                headers=admin_header,
            )
            assert second_resolve.status_code == HTTP_200_OK, second_resolve.text
            assert second_resolve.json()["id"] == second_question["id"]
            assert second_resolve.json()["groupId"] == group["id"]
            assert second_resolve.json()["cqCatalogueIdentifier"] == "A.2"
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_removed_cq_catalogue_identifier_is_not_reused(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        admin_header = login(client)
        project = create_project(client, admin_header, engineers=[ENGINEER_EMAIL])
        group = create_group(client, admin_header, project["id"])
        first_question = create_question(client, admin_header, group["id"])
        second_question = create_question(client, admin_header, group["id"])
        engineer_header = login(client, ENGINEER_EMAIL)

        try:
            topic = create_topic(client, engineer_header, project["id"], identifier="A")

            first_assign = client.post(
                f"/topics/{project['id']}/{topic['id']}/questions/{first_question['id']}",
                headers=engineer_header,
            )
            assert first_assign.status_code == HTTP_200_OK, first_assign.text
            assert first_assign.json()["cqCatalogueIdentifier"] == "A.1"

            remove_response = client.delete(
                f"/topics/{project['id']}/questions/{first_question['id']}",
                headers=engineer_header,
            )
            assert remove_response.status_code == HTTP_200_OK, remove_response.text
            assert remove_response.json()["cqCatalogueIdentifier"] is None

            unassigned_resolve = client.get(
                f"/questions/by_project/{project['id']}/catalogue/A.1",
                headers=engineer_header,
            )
            assert unassigned_resolve.status_code == 404, unassigned_resolve.text

            second_assign = client.post(
                f"/topics/{project['id']}/{topic['id']}/questions/{second_question['id']}",
                headers=engineer_header,
            )
            assert second_assign.status_code == HTTP_200_OK, second_assign.text
            assert second_assign.json()["cqCatalogueIdentifier"] == "A.2"
        finally:
            client.delete(f"/projects/{project['id']}", headers=login(client))


def test_question_detail_loads_catalogue_identifier_for_consolidated_questions(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        admin_header = login(client)
        project = create_project(client, admin_header, engineers=[ENGINEER_EMAIL])
        group = create_group(client, admin_header, project["id"])
        first_question = create_question(client, admin_header, group["id"])
        second_question = create_question(client, admin_header, group["id"])
        engineer_header = login(client, ENGINEER_EMAIL)

        try:
            topic = create_topic(client, engineer_header, project["id"], identifier="A")
            assign_response = client.post(
                f"/topics/{project['id']}/{topic['id']}/questions/{first_question['id']}",
                headers=engineer_header,
            )
            assert assign_response.status_code == HTTP_200_OK, assign_response.text

            create_consolidation(
                client,
                admin_header,
                project["id"],
                question_ids=[first_question["id"], second_question["id"]],
                target_question={"question": unique_text("Consolidated target?")},
            )

            detail_response = client.get(
                f"/questions/{second_question['id']}",
                headers=admin_header,
            )
            assert detail_response.status_code == HTTP_200_OK, detail_response.text
            consolidation = detail_response.json()["consolidations"][0]
            consolidated_questions = consolidation["sourceQuestions"]
            catalogued_question = next(
                question for question in consolidated_questions if question["id"] == first_question["id"]
            )
            assert catalogued_question["cqCatalogueIdentifier"] == "A.1"
            assert {question["id"] for question in consolidated_questions} == {
                first_question["id"],
                second_question["id"],
            }
        finally:
            client.delete(f"/projects/{project['id']}", headers=login(client))
