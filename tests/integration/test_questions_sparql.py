from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED
from litestar.testing import TestClient

from ._fixtures import admin_header, test_client  # pyright: ignore


GROUP_ID = "b0488a1e-3768-4d34-8c90-f24f1f9036a3"
QUESTION_ID = "2de6c0c8-3565-4c5a-bc85-3b5971e0e452"


def test_create_and_update_question_sparql(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        create_query = "SELECT ?s WHERE { ?s ?p ?o } LIMIT 10"
        create_response = client.post(
            f"/questions/{GROUP_ID}",
            json={
                "question": "Which resources are available?",
                "sparqlQuery": create_query,
            },
            headers=admin_header,
        )
        assert create_response.status_code == HTTP_201_CREATED
        assert create_response.json()["sparqlQuery"] == create_query

        question_id = create_response.json()["id"]
        update_query = "ASK { ?s a ?type }"
        update_response = client.put(
            f"/questions/{GROUP_ID}/{question_id}",
            json={
                "question": "Which resources are available now?",
                "sparqlQuery": update_query,
            },
            headers=admin_header,
        )
        assert update_response.status_code == HTTP_200_OK
        assert update_response.json()["sparqlQuery"] == update_query


def test_get_question_detail_loads_editor(
    test_client: TestClient[Litestar],
    admin_header,
) -> None:
    with test_client as client:
        response = client.get(
            f"/questions/{GROUP_ID}/{QUESTION_ID}",
            headers=admin_header,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["editor"]["id"] is not None
