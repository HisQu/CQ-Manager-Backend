from uuid import uuid4

from litestar import Litestar
from litestar.status_codes import HTTP_200_OK
from litestar.testing import TestClient

from ._fixtures import (
    admin_header,
    create_consolidation,
    create_project_group,
    create_question,
    test_client,
)  # pyright: ignore


def _create_consolidated_questions(
    client: TestClient[Litestar],
    admin_header,
) -> tuple[dict, dict, dict, list[dict]]:
    project, group = create_project_group(client, admin_header)
    questions = [
        create_question(client, admin_header, group["id"], question=f"Source {uuid4().hex}") for _ in range(2)
    ]
    consolidation = create_consolidation(
        client,
        admin_header,
        project["id"],
        question_ids=[question["id"] for question in questions],
        result_question={
            "question": f"Consolidated {uuid4().hex}",
            "reference": "S. 138.",
            "anchor": "S. 138 Abs. 4 - Kanzlei.",
            "exampleAnswer": "Nikolaus Hertnid.",
            "type": "VCQ",
        },
    )
    return project, group, consolidation, questions


def test_get_group_questions_unified(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        project, group, consolidation, questions = _create_consolidated_questions(client, admin_header)
        consolidated_ids = {question["id"] for question in questions}

        try:
            unified = client.get(
                f"/questions/{group['id']}/unified",
                headers=admin_header,
            )
            assert unified.status_code == HTTP_200_OK

            results = unified.json()
            consolidation_results = [
                result
                for result in results
                if result["unifiedEntryKind"] == "consolidation_result"
                and result["consolidationId"] == consolidation["id"]
            ]
            assert len(consolidation_results) == 1
            assert consolidation_results[0]["id"] == consolidation["resultQuestion"]["id"]
            assert consolidation_results[0]["consolidationId"] == consolidation["id"]
            assert set(consolidation_results[0]["consolidatedQuestionIds"]) == consolidated_ids
            assert consolidation_results[0]["reference"] == "S. 138."
            assert consolidation_results[0]["anchor"] == "S. 138 Abs. 4 - Kanzlei."
            assert consolidation_results[0]["exampleAnswer"] == "Nikolaus Hertnid."
            assert consolidation_results[0]["type"] == "VCQ"

            question_entries = [result for result in results if result["unifiedEntryKind"] == "question"]
            assert all(question["id"] not in consolidated_ids for question in question_entries)
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_get_project_questions_unified(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        project, _, consolidation, questions = _create_consolidated_questions(client, admin_header)
        consolidated_ids = {question["id"] for question in questions}
        result_question_id = consolidation["resultQuestion"]["id"]

        try:
            unified = client.get(
                f"/questions/by_project/{project['id']}/unified",
                headers=admin_header,
            )
            assert unified.status_code == HTTP_200_OK

            results = unified.json()
            question_entries = [question for question in results if question["unifiedEntryKind"] == "question"]
            consolidation_entries = [
                question for question in results if question["unifiedEntryKind"] == "consolidation_result"
            ]

            assert all(
                question["id"] not in consolidated_ids and question["id"] != result_question_id
                for question in question_entries
            )
            assert len(consolidation_entries) == 1
            assert consolidation_entries[0]["id"] == result_question_id
            assert set(consolidation_entries[0]["consolidatedQuestionIds"]) == consolidated_ids
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
