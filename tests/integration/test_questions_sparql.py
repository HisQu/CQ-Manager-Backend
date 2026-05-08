from litestar import Litestar
from litestar.status_codes import HTTP_200_OK
from litestar.testing import TestClient

from ._fixtures import (
    admin_header,
    create_project_group,
    create_question,
    test_client,
)  # pyright: ignore


def test_create_and_update_question_sparql(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        project, group = create_project_group(client, admin_header)

        try:
            create_query = "SELECT ?s WHERE { ?s ?p ?o } LIMIT 10"
            question = create_question(
                client,
                admin_header,
                group["id"],
                question="Which resources are available?",
                sparql_query=create_query,
            )
            assert question["sparqlQuery"] == create_query

            update_query = "ASK { ?s a ?type }"
            update_response = client.put(
                f"/questions/{group['id']}/{question['id']}",
                json={
                    "question": "Which resources are available now?",
                    "sparqlQuery": update_query,
                },
                headers=admin_header,
            )
            assert update_response.status_code == HTTP_200_OK
            assert update_response.json()["sparqlQuery"] == update_query
            assert update_response.json()["versions"][0]["editor"]["id"] is not None
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_question_comment_can_be_created_and_updated(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        project, group = create_project_group(client, admin_header)
        comment = "\n".join(
            [
                "Initial competency question comment.",
                "This field can hold longer notes with line breaks.",
                "It is separate from the comments list.",
            ]
        )
        updated_comment = f"{comment}\n\nFollow-up note."

        try:
            question = create_question(
                client,
                admin_header,
                group["id"],
                comment=comment,
            )
            assert question["comment"] == comment
            assert question["comments"] == []

            detail_response = client.get(
                f"/questions/{group['id']}/{question['id']}",
                headers=admin_header,
            )
            assert detail_response.status_code == HTTP_200_OK
            assert detail_response.json()["comment"] == comment
            assert detail_response.json()["comments"] == []

            update_response = client.put(
                f"/questions/{group['id']}/{question['id']}",
                json={"comment": updated_comment},
                headers=admin_header,
            )
            assert update_response.status_code == HTTP_200_OK, update_response.text
            assert update_response.json()["question"] == question["question"]
            assert update_response.json()["comment"] == updated_comment

            clear_response = client.put(
                f"/questions/{group['id']}/{question['id']}",
                json={"comment": None},
                headers=admin_header,
            )
            assert clear_response.status_code == HTTP_200_OK, clear_response.text
            assert clear_response.json()["comment"] is None
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_get_question_detail_loads_editor(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        project, group = create_project_group(client, admin_header)
        question = create_question(client, admin_header, group["id"])

        try:
            response = client.get(
                f"/questions/{group['id']}/{question['id']}",
                headers=admin_header,
            )
            assert response.status_code == HTTP_200_OK
            assert response.json()["editor"]["id"] is not None
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
