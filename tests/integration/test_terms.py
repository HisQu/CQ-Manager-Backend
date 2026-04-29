from uuid import uuid4

from httpx import Headers
from litestar import Litestar
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_401_UNAUTHORIZED,
)
from litestar.testing import TestClient

from ._fixtures import test_client  # pyright: ignore


PROJECT_ID = "7efa96ba-c7a9-4069-9728-dc7fa2c105fd"
QUESTION_ID = "92bcacac-c5bf-4fe3-a12a-d52d5f3ac1f1"


def _login(client: TestClient[Litestar], email: str) -> Headers:
    response = client.post(
        "/users/login",
        json={"email": email, "password": "HalloWelt123"},
    )
    assert response.status_code == HTTP_201_CREATED
    assert response.headers.get("Authorization", None) is not None
    return response.headers


def _add_annotation(
    client: TestClient[Litestar],
    headers: Headers,
    term: str,
    passage: str,
) -> tuple[str, str]:
    response = client.put(
        f"/terms/add/{QUESTION_ID}",
        json={"annotations": [{"term": term, "passage": passage}]},
        headers=headers,
    )
    assert response.status_code == HTTP_200_OK

    annotations = response.json()
    selected = next(
        filter(lambda annotation: annotation["content"] == passage, annotations), None
    )
    assert selected is not None

    term_response = client.get(f"/terms/project/{PROJECT_ID}", headers=headers)
    assert term_response.status_code == HTTP_200_OK
    terms = term_response.json()
    selected_term = next(filter(lambda item: item["content"] == term, terms), None)
    assert selected_term is not None

    return selected["id"], selected_term["id"]


def test_update_annotation_requires_engineer(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        manager_header = _login(client, "chiara@uni-jena.de")
        response = client.put(
            f"/terms/{PROJECT_ID}/{QUESTION_ID}/{uuid4()}",
            json={"term": "Updated Term", "passage": "Updated Passage"},
            headers=manager_header,
        )
        assert response.status_code == HTTP_401_UNAUTHORIZED


def test_update_annotation_with_engineer(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        engineer_header = _login(client, "malte@uni-jena.de")
        unique = uuid4().hex
        original_term = f"term-{unique}"
        original_passage = f"passage-{unique}"
        updated_term = f"updated-term-{unique}"
        updated_passage = f"updated-passage-{unique}"

        passage_id, _ = _add_annotation(
            client, engineer_header, original_term, original_passage
        )

        response = client.put(
            f"/terms/{PROJECT_ID}/{QUESTION_ID}/{passage_id}",
            json={"term": updated_term, "passage": updated_passage},
            headers=engineer_header,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["content"] == updated_passage

        passages_response = client.get(
            f"/terms/question/{QUESTION_ID}", headers=engineer_header
        )
        assert passages_response.status_code == HTTP_200_OK
        passages = passages_response.json()
        assert any(item["content"] == updated_passage for item in passages)


def test_update_term_requires_engineer(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        engineer_header = _login(client, "malte@uni-jena.de")
        manager_header = _login(client, "chiara@uni-jena.de")
        unique = uuid4().hex
        term = f"term-for-update-{unique}"
        passage = f"passage-for-update-{unique}"

        _, term_id = _add_annotation(client, engineer_header, term, passage)

        response = client.put(
            f"/terms/{PROJECT_ID}/{term_id}",
            json={"content": f"changed-{term}"},
            headers=manager_header,
        )
        assert response.status_code == HTTP_401_UNAUTHORIZED


def test_update_term_with_engineer(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        engineer_header = _login(client, "malte@uni-jena.de")
        unique = uuid4().hex
        original_term = f"term-edit-{unique}"
        updated_term = f"term-edited-{unique}"
        passage = f"passage-edit-{unique}"

        _, term_id = _add_annotation(client, engineer_header, original_term, passage)

        response = client.put(
            f"/terms/{PROJECT_ID}/{term_id}",
            json={"content": updated_term},
            headers=engineer_header,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["content"] == updated_term


def test_delete_term_requires_engineer(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        engineer_header = _login(client, "malte@uni-jena.de")
        manager_header = _login(client, "chiara@uni-jena.de")
        unique = uuid4().hex
        term = f"term-delete-denied-{unique}"
        passage = f"passage-delete-denied-{unique}"

        _, term_id = _add_annotation(client, engineer_header, term, passage)

        response = client.delete(
            f"/terms/{PROJECT_ID}/{term_id}", headers=manager_header
        )
        assert response.status_code == HTTP_401_UNAUTHORIZED


def test_delete_term_with_engineer(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        engineer_header = _login(client, "malte@uni-jena.de")
        unique = uuid4().hex
        term = f"term-delete-{unique}"
        passage = f"passage-delete-{unique}"

        passage_id, term_id = _add_annotation(client, engineer_header, term, passage)

        response = client.delete(
            f"/terms/{PROJECT_ID}/{term_id}", headers=engineer_header
        )
        assert response.status_code == HTTP_204_NO_CONTENT

        term_response = client.get(
            f"/terms/project/{PROJECT_ID}", headers=engineer_header
        )
        assert term_response.status_code == HTTP_200_OK
        assert not any(item["id"] == term_id for item in term_response.json())

        passages_response = client.get(
            f"/terms/question/{QUESTION_ID}", headers=engineer_header
        )
        assert passages_response.status_code == HTTP_200_OK
        assert not any(item["id"] == passage_id for item in passages_response.json())
