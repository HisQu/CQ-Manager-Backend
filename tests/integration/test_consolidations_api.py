from uuid import uuid4

from litestar import Litestar
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_404_NOT_FOUND,
)
from litestar.testing import TestClient

from ._fixtures import (
    create_consolidation,
    create_group,
    create_project,
    create_project_group,
    create_question,
    test_client,
    admin_header,
)  # pyright: ignore


def _create_project_with_questions(
    client: TestClient[Litestar],
    admin_header,
    *,
    count: int = 2,
) -> tuple[dict, dict, list[dict]]:
    project, group = create_project_group(client, admin_header)
    questions = [
        create_question(client, admin_header, group["id"], question=f"Source {uuid4().hex}") for _ in range(count)
    ]
    return project, group, questions


def test_get_consolidation_includes_questions(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        project, _, questions = _create_project_with_questions(client, admin_header)
        question_ids = [question["id"] for question in questions]

        try:
            created = create_consolidation(
                client,
                admin_header,
                project["id"],
                question_ids=question_ids,
                result_question={"question": f"Result {uuid4().hex}"},
            )

            response = client.get(
                f"/consolidations/{project['id']}/{created['id']}",
                headers=admin_header,
            )

            assert response.status_code == HTTP_200_OK, response.text
            consolidation = response.json()
            assert consolidation["id"] == created["id"]
            assert consolidation["resultQuestion"]["id"] == created["resultQuestion"]["id"]
            assert {question["id"] for question in consolidation["questions"]} == set(question_ids)
            assert all("question" in question for question in consolidation["questions"])
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_create_consolidation_with_existing_target_question_id(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        project, group, questions = _create_project_with_questions(client, admin_header, count=1)
        target = create_question(
            client,
            admin_header,
            group["id"],
            question=f"Existing target {uuid4().hex}",
        )

        try:
            consolidation_response = client.post(
                f"/consolidations/{project['id']}",
                json={
                    "resultQuestion": {"id": target["id"]},
                    "ids": [questions[0]["id"]],
                },
                headers=admin_header,
            )

            assert consolidation_response.status_code == HTTP_201_CREATED, consolidation_response.text
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_create_consolidation_infers_result_question_group(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        project, group, questions = _create_project_with_questions(client, admin_header, count=1)
        source_id = questions[0]["id"]

        try:
            consolidation = create_consolidation(
                client,
                admin_header,
                project["id"],
                question_ids=[source_id],
                result_question={"question": "Test"},
            )

            assert consolidation["resultQuestion"]["question"] == "Test"
            assert [question["id"] for question in consolidation["questions"]] == [source_id]

            result_question = client.get(
                f"/questions/{group['id']}/{consolidation['resultQuestion']['id']}",
                headers=admin_header,
            )
            assert result_question.status_code == HTTP_200_OK, result_question.text
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_deleting_project_deletes_consolidations(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])
        question = create_question(client, admin_header, group["id"])
        consolidation = create_consolidation(
            client,
            admin_header,
            project["id"],
            question_ids=[question["id"]],
            result_question={"question": f"Result question {uuid4().hex}"},
        )

        try:
            delete_response = client.delete(f"/projects/{project['id']}", headers=admin_header)
            assert delete_response.status_code == HTTP_204_NO_CONTENT, delete_response.text

            deleted_consolidation = client.get(
                f"/consolidations/{project['id']}/{consolidation['id']}",
                headers=admin_header,
            )
            assert deleted_consolidation.status_code == HTTP_404_NOT_FOUND, deleted_consolidation.text
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
