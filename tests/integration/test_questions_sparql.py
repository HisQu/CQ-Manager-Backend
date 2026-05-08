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
