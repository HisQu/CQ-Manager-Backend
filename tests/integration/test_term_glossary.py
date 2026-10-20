from httpx import Headers
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT
from litestar.testing import TestClient

from ._fixtures import admin_header, create_group, create_project, login, test_client, unique_text


def _annotated_question(client: TestClient[Litestar], headers: Headers, group_id: str, *terms: str) -> dict:
    """Creates a question whose text is `terms` joined by spaces, annotating every word with its term."""
    annotations, start = [], 0
    for term in terms:
        annotations.append({"passage": term, "term": term, "start": start, "end": start + len(term)})
        start += len(term) + 1
    response = client.post(
        f"/questions/by_group/{group_id}",
        json={"question": " ".join(terms), "annotations": annotations},
        headers=headers,
    )
    assert response.status_code == HTTP_201_CREATED, response.text
    return response.json()


def _terms(client: TestClient[Litestar], headers: Headers, project_id: str) -> list[dict]:
    response = client.get(f"/terms/project/{project_id}", headers=headers)
    assert response.status_code == HTTP_200_OK, response.text
    return response.json()


def _usage(client: TestClient[Litestar], headers: Headers, project_id: str) -> dict[str, int]:
    return {term["content"]: term["noQuestions"] for term in _terms(client, headers, project_id)}


def test_project_terms_report_how_many_questions_use_them(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        admin_header = login(client)
        project = create_project(client, admin_header)
        other_project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])
        other_group = create_group(client, admin_header, other_project["id"])
        used, rare, unused = unique_text("Pfründe"), unique_text("Ablass"), unique_text("Petent")

        try:
            # Repeated annotations in one question count once.
            _annotated_question(client, admin_header, group["id"], used, used, rare)
            _annotated_question(client, admin_header, group["id"], used)
            deleted = _annotated_question(client, admin_header, group["id"], used, rare)
            response = client.delete(f"/questions/{deleted['id']}", headers=admin_header)
            assert response.status_code == HTTP_204_NO_CONTENT, response.text
            # Terms of another project are counted there, not here.
            _annotated_question(client, admin_header, other_group["id"], used)
            response = client.post(f"/terms/project/{project['id']}", json={"content": unused}, headers=admin_header)
            assert response.status_code == HTTP_201_CREATED, response.text

            assert _usage(client, admin_header, project["id"]) == {used: 2, rare: 1, unused: 0}
            assert _usage(client, admin_header, other_project["id"]) == {used: 1}

            # The count matches the term's occurrence list.
            term_ids = {term["content"]: term["id"] for term in _terms(client, admin_header, project["id"])}
            response = client.get(f"/terms/{project['id']}/{term_ids[used]}", headers=admin_header)
            assert response.status_code == HTTP_200_OK, response.text
            assert len(response.json()) == 2
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
            client.delete(f"/projects/{other_project['id']}", headers=admin_header)


def test_update_term_replaces_definition_and_iri(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        admin_header = login(client)
        project = create_project(client, admin_header)
        content = unique_text("Pfründe")

        try:
            response = client.post(
                f"/terms/project/{project['id']}",
                json={"content": content, "definition": "Benefice", "conceptIri": "https://example.org/Benefice"},
                headers=admin_header,
            )
            assert response.status_code == HTTP_201_CREATED, response.text
            term_id = response.json()["id"]

            response = client.put(
                f"/terms/{project['id']}/{term_id}",
                json={"content": content, "definition": "Church office", "conceptIri": "https://example.org/Office"},
                headers=admin_header,
            )
            assert response.status_code == HTTP_200_OK, response.text
            assert (response.json()["definition"], response.json()["conceptIri"]) == ("Church office", "https://example.org/Office")

            response = client.put(
                f"/terms/{project['id']}/{term_id}",
                json={"content": content, "definition": None, "conceptIri": None},
                headers=admin_header,
            )
            assert response.status_code == HTTP_200_OK, response.text
            assert (response.json()["definition"], response.json()["conceptIri"]) == (None, None)
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
