from uuid import uuid4

from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED
from litestar.testing import TestClient

from ._fixtures import admin_header, test_client  # pyright: ignore


PROJECT_ID = "7efa96ba-c7a9-4069-9728-dc7fa2c105fd"
GROUP_ID = "a825cd37-f637-4853-bc73-97a2b01f18e7"
KEBAB_PROJECT_ID = "415de6a4-4d35-420a-bca2-0fde2731234d"
KEBAB_GROUP_ID = "b0488a1e-3768-4d34-8c90-f24f1f9036a3"
SOURCE_QUESTION_ID = "a36783cf-1fb4-4e52-a19f-fe74a348e833"
CONSOLIDATION_ID = "5daa6935-bd94-47fa-87d8-e0660ef00a79"
CONSOLIDATION_RESULT_QUESTION_ID = "4f8c5f0b-5966-49d6-8d0f-a9a2e7883114"
CONSOLIDATED_QUESTION_IDS = {
    "92bcacac-c5bf-4fe3-a12a-d52d5f3ac1f1",
    "968b9a07-463d-4e0d-a2ea-ba39c06e830d",
}


def test_get_consolidation_includes_questions(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        response = client.get(
            f"/consolidations/{PROJECT_ID}/{CONSOLIDATION_ID}",
            headers=admin_header,
        )

        assert response.status_code == HTTP_200_OK, response.text
        consolidation = response.json()
        assert consolidation["id"] == CONSOLIDATION_ID
        assert consolidation["resultQuestion"]["id"] == CONSOLIDATION_RESULT_QUESTION_ID
        assert {question["id"] for question in consolidation["questions"]} == CONSOLIDATED_QUESTION_IDS
        assert all("question" in question for question in consolidation["questions"])
        assert all("author" in question for question in consolidation["questions"])


def test_create_consolidation_with_existing_target_question_id(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        question_response = client.post(
            f"/questions/{GROUP_ID}",
            json={"question": f"Existing target {uuid4().hex}"},
            headers=admin_header,
        )
        assert question_response.status_code == HTTP_201_CREATED
        target_id = question_response.json()["id"]

        consolidation_response = client.post(
            f"/consolidations/{PROJECT_ID}",
            json={
                "resultQuestion": {"id": target_id},
                "ids": [SOURCE_QUESTION_ID],
            },
            headers=admin_header,
        )

        assert consolidation_response.status_code == HTTP_201_CREATED, consolidation_response.text


def test_create_consolidation_infers_result_question_group(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        source_response = client.post(
            f"/questions/{KEBAB_GROUP_ID}",
            json={"question": f"Source {uuid4().hex}"},
            headers=admin_header,
        )
        assert source_response.status_code == HTTP_201_CREATED
        source_id = source_response.json()["id"]

        consolidation_response = client.post(
            f"/consolidations/{KEBAB_PROJECT_ID}",
            json={
                "resultQuestion": {"question": "Test"},
                "ids": [source_id],
            },
            headers=admin_header,
        )

        assert consolidation_response.status_code == HTTP_201_CREATED, consolidation_response.text
        consolidation = consolidation_response.json()
        assert consolidation["resultQuestion"]["question"] == "Test"
        assert consolidation["resultQuestion"]["group"]["id"] == KEBAB_GROUP_ID
        assert [question["id"] for question in consolidation["questions"]] == [source_id]
