from litestar import Litestar
from litestar.status_codes import HTTP_200_OK
from litestar.testing import TestClient

from ._fixtures import admin_header, test_client  # pyright: ignore


GROUP_WITH_CONSOLIDATED = "a825cd37-f637-4853-bc73-97a2b01f18e7"
PROJECT_WITH_CONSOLIDATED = "7efa96ba-c7a9-4069-9728-dc7fa2c105fd"
CONSOLIDATION_RESULT = "5daa6935-bd94-47fa-87d8-e0660ef00a79"
CONSOLIDATION_RESULT_QUESTION = "4f8c5f0b-5966-49d6-8d0f-a9a2e7883114"
CONSOLIDATED_SET = {
    "92bcacac-c5bf-4fe3-a12a-d52d5f3ac1f1",
    "968b9a07-463d-4e0d-a2ea-ba39c06e830d",
}


def test_get_group_questions_unified(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        unified = client.get(
            f"/questions/{GROUP_WITH_CONSOLIDATED}/unified",
            headers=admin_header,
        )
        assert unified.status_code == HTTP_200_OK

        results = unified.json()
        consolidation_results = [
            result
            for result in results
            if result["unifiedEntryKind"] == "consolidation_result"
            and result["consolidationId"] == CONSOLIDATION_RESULT
        ]
        assert len(consolidation_results) == 1
        assert consolidation_results[0]["id"] == CONSOLIDATION_RESULT_QUESTION
        assert consolidation_results[0]["consolidationId"] == CONSOLIDATION_RESULT
        assert (
            set(consolidation_results[0]["consolidatedQuestionIds"]) == CONSOLIDATED_SET
        )

        question_entries = [
            result for result in results if result["unifiedEntryKind"] == "question"
        ]
        assert all(question["id"] not in CONSOLIDATED_SET for question in question_entries)


def test_get_project_questions_unified(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        unified = client.get(
            f"/questions/by_project/{PROJECT_WITH_CONSOLIDATED}/unified",
            headers=admin_header,
        )
        assert unified.status_code == HTTP_200_OK

        results = unified.json()
        question_entries = [
            question
            for question in results
            if question["unifiedEntryKind"] == "question"
        ]
        consolidation_entries = [
            question
            for question in results
            if question["unifiedEntryKind"] == "consolidation_result"
        ]

        assert all(
            question["id"] not in CONSOLIDATED_SET
            and question["id"] != CONSOLIDATION_RESULT_QUESTION
            for question in question_entries
        )
        assert len(consolidation_entries) == 1
        assert consolidation_entries[0]["id"] == CONSOLIDATION_RESULT_QUESTION
        assert set(consolidation_entries[0]["consolidatedQuestionIds"]) == CONSOLIDATED_SET
