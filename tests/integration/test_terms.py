from uuid import uuid4

from httpx import Headers
from litestar import Litestar
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_401_UNAUTHORIZED,
)
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
)  # pyright: ignore


def _create_terms_context(
    client: TestClient[Litestar],
    admin_header: Headers,
) -> tuple[dict, dict, dict, Headers, Headers]:
    project = create_project(
        client,
        admin_header,
        managers=[MANAGER_EMAIL],
        engineers=[ENGINEER_EMAIL],
    )
    engineer_header = login(client, ENGINEER_EMAIL)
    manager_header = login(client, MANAGER_EMAIL)
    group = create_group(client, engineer_header, project["id"])
    question = create_question(client, engineer_header, group["id"])
    return project, group, question, engineer_header, manager_header


def _add_annotation(
    client: TestClient[Litestar],
    headers: Headers,
    project_id: str,
    question_id: str,
    term: str,
    passage: str,
) -> tuple[str, str]:
    response = client.put(
        f"/terms/add/{question_id}",
        json={"annotations": [{"term": term, "passage": passage}]},
        headers=headers,
    )
    assert response.status_code == HTTP_200_OK

    annotations = response.json()
    selected = next(filter(lambda annotation: annotation["content"] == passage, annotations), None)
    assert selected is not None

    term_response = client.get(f"/terms/project/{project_id}", headers=headers)
    assert term_response.status_code == HTTP_200_OK
    terms = term_response.json()
    selected_term = next(filter(lambda item: item["content"] == term, terms), None)
    assert selected_term is not None

    return selected["id"], selected_term["id"]


def test_update_annotation_requires_engineer(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project, _, question, _, manager_header = _create_terms_context(client, admin_header)

        try:
            response = client.put(
                f"/terms/{project['id']}/{question['id']}/{uuid4()}",
                json={"term": "Updated Term", "passage": "Updated Passage"},
                headers=manager_header,
            )
            assert response.status_code == HTTP_401_UNAUTHORIZED
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_update_annotation_with_engineer(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project, _, question, engineer_header, _ = _create_terms_context(client, admin_header)
        unique = uuid4().hex
        original_term = f"term-{unique}"
        original_passage = f"passage-{unique}"
        updated_term = f"updated-term-{unique}"
        updated_passage = f"updated-passage-{unique}"

        try:
            passage_id, _ = _add_annotation(
                client,
                engineer_header,
                project["id"],
                question["id"],
                original_term,
                original_passage,
            )

            response = client.put(
                f"/terms/{project['id']}/{question['id']}/{passage_id}",
                json={"term": updated_term, "passage": updated_passage},
                headers=engineer_header,
            )
            assert response.status_code == HTTP_200_OK
            assert response.json()["content"] == updated_passage

            passages_response = client.get(f"/terms/question/{question['id']}", headers=engineer_header)
            assert passages_response.status_code == HTTP_200_OK
            passages = passages_response.json()
            assert any(item["content"] == updated_passage for item in passages)
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_update_term_requires_engineer(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project, _, question, engineer_header, manager_header = _create_terms_context(client, admin_header)
        unique = uuid4().hex
        term = f"term-for-update-{unique}"
        passage = f"passage-for-update-{unique}"

        try:
            _, term_id = _add_annotation(
                client,
                engineer_header,
                project["id"],
                question["id"],
                term,
                passage,
            )

            response = client.put(
                f"/terms/{project['id']}/{term_id}",
                json={"content": f"changed-{term}"},
                headers=manager_header,
            )
            assert response.status_code == HTTP_401_UNAUTHORIZED
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_update_term_with_engineer(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project, _, question, engineer_header, _ = _create_terms_context(client, admin_header)
        unique = uuid4().hex
        original_term = f"term-edit-{unique}"
        updated_term = f"term-edited-{unique}"
        passage = f"passage-edit-{unique}"

        try:
            _, term_id = _add_annotation(
                client,
                engineer_header,
                project["id"],
                question["id"],
                original_term,
                passage,
            )

            response = client.put(
                f"/terms/{project['id']}/{term_id}",
                json={"content": updated_term},
                headers=engineer_header,
            )
            assert response.status_code == HTTP_200_OK
            assert response.json()["content"] == updated_term
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_delete_term_requires_engineer(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project, _, question, engineer_header, manager_header = _create_terms_context(client, admin_header)
        unique = uuid4().hex
        term = f"term-delete-denied-{unique}"
        passage = f"passage-delete-denied-{unique}"

        try:
            _, term_id = _add_annotation(
                client,
                engineer_header,
                project["id"],
                question["id"],
                term,
                passage,
            )

            response = client.delete(f"/terms/{project['id']}/{term_id}", headers=manager_header)
            assert response.status_code == HTTP_401_UNAUTHORIZED
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_delete_term_with_engineer(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project, _, question, engineer_header, _ = _create_terms_context(client, admin_header)
        unique = uuid4().hex
        term = f"term-delete-{unique}"
        passage = f"passage-delete-{unique}"

        try:
            passage_id, term_id = _add_annotation(
                client,
                engineer_header,
                project["id"],
                question["id"],
                term,
                passage,
            )

            response = client.delete(f"/terms/{project['id']}/{term_id}", headers=engineer_header)
            assert response.status_code == HTTP_204_NO_CONTENT

            term_response = client.get(f"/terms/project/{project['id']}", headers=engineer_header)
            assert term_response.status_code == HTTP_200_OK
            assert not any(item["id"] == term_id for item in term_response.json())

            passages_response = client.get(f"/terms/question/{question['id']}", headers=engineer_header)
            assert passages_response.status_code == HTTP_200_OK
            assert not any(item["id"] == passage_id for item in passages_response.json())
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
