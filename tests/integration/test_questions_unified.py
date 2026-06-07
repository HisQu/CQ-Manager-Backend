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
        target_question={
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
                f"/questions/by_group/{group['id']}/unified",
                headers=admin_header,
            )
            assert unified.status_code == HTTP_200_OK

            results = unified.json()
            consolidation_results = [
                result
                for result in results
                if result["unifiedEntryKind"] == "consolidation_result"
                and result["consolidation"]["id"] == consolidation["id"]
            ]
            assert len(consolidation_results) == 1
            assert consolidation_results[0]["id"] == consolidation["targetQuestion"]["id"]
            assert consolidation_results[0]["consolidation"]["role"] == "target"
            assert (
                consolidation_results[0]["consolidation"]["targetQuestionId"] == consolidation["targetQuestion"]["id"]
            )
            assert set(consolidation_results[0]["consolidation"]["sourceQuestionIds"]) == consolidated_ids
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
        target_question_id = consolidation["targetQuestion"]["id"]

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
                question["id"] not in consolidated_ids and question["id"] != target_question_id
                for question in question_entries
            )
            assert len(consolidation_entries) == 1
            assert consolidation_entries[0]["id"] == target_question_id
            assert consolidation_entries[0]["consolidation"]["role"] == "target"
            assert consolidation_entries[0]["consolidation"]["targetQuestionId"] == target_question_id
            assert set(consolidation_entries[0]["consolidation"]["sourceQuestionIds"]) == consolidated_ids
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_plain_question_responses_include_consolidation_context(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        project, group, consolidation, questions = _create_consolidated_questions(client, admin_header)
        source_ids = {question["id"] for question in questions}
        target_question_id = consolidation["targetQuestion"]["id"]

        try:
            list_response = client.get(
                f"/questions/by_group/{group['id']}",
                headers=admin_header,
            )
            assert list_response.status_code == HTTP_200_OK, list_response.text

            listed_questions = list_response.json()
            source_entry = next(question for question in listed_questions if question["id"] == questions[0]["id"])
            target_entry = next(question for question in listed_questions if question["id"] == target_question_id)

            source_context = source_entry["consolidations"][0]
            assert source_context["id"] == consolidation["id"]
            assert source_context["role"] == "source"
            assert source_context["targetQuestionId"] == target_question_id
            assert set(source_context["sourceQuestionIds"]) == source_ids

            target_context = target_entry["consolidations"][0]
            assert target_context["id"] == consolidation["id"]
            assert target_context["role"] == "target"
            assert target_context["targetQuestionId"] == target_question_id
            assert set(target_context["sourceQuestionIds"]) == source_ids

            detail_response = client.get(
                f"/questions/{questions[1]['id']}",
                headers=admin_header,
            )
            assert detail_response.status_code == HTTP_200_OK, detail_response.text
            detail_consolidation = detail_response.json()["consolidations"][0]
            assert detail_consolidation["id"] == consolidation["id"]
            assert detail_consolidation["targetQuestion"]["id"] == target_question_id
            assert detail_consolidation["targetQuestion"]["question"] == consolidation["targetQuestion"]["question"]
            assert {question["id"] for question in detail_consolidation["sourceQuestions"]} == source_ids
            assert detail_consolidation["noSourceQuestions"] == len(source_ids)
            assert detail_consolidation["project"]["id"] == project["id"]
            assert "engineer" in detail_consolidation
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_question_listings_include_discussion_comment_count(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        project, group = create_project_group(client, admin_header)
        question = create_question(client, admin_header, group["id"])

        try:
            for comment in ("First discussion comment.", "Second discussion comment."):
                response = client.post(
                    "/comments/",
                    json={"questionId": question["id"], "comment": comment},
                    headers=admin_header,
                )
                assert response.status_code < 300, response.text

            list_response = client.get(
                f"/questions/by_group/{group['id']}",
                headers=admin_header,
            )
            assert list_response.status_code == HTTP_200_OK, list_response.text
            listed_question = next(item for item in list_response.json() if item["id"] == question["id"])
            assert listed_question["noComments"] == 2

            unified_response = client.get(
                f"/questions/by_group/{group['id']}/unified",
                headers=admin_header,
            )
            assert unified_response.status_code == HTTP_200_OK, unified_response.text
            unified_question = next(item for item in unified_response.json() if item["id"] == question["id"])
            assert unified_question["noComments"] == 2
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
