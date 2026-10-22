from httpx import Headers
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED
from litestar.testing import TestClient

from ._fixtures import admin_header, create_group, create_project, login, test_client, unique_text


def _revise(client: TestClient[Litestar], headers: Headers, question_id: str, text: str) -> dict:
    return _revise_with(client, headers, question_id, {"question": text})


def _revise_with(client: TestClient[Litestar], headers: Headers, question_id: str, payload: dict) -> dict:
    response = client.put(f"/questions/{question_id}", json=payload, headers=headers)
    assert response.status_code == HTTP_200_OK, response.text
    return max(response.json()["revisions"], key=lambda revision: revision["versionNumber"])


def _spans(revision: dict) -> list[tuple[str, int, int]]:
    annotations = [annotation for version in revision["annotationVersions"] for annotation in version["annotations"]]
    return sorted((item["content"], item["start"], item["end"]) for item in annotations)


def test_revision_keeps_annotations_that_still_match(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        admin_header = login(client)
        project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])
        first, second = unique_text("Pfründe"), unique_text("Petent")
        text = f"{first} {second}"

        try:
            response = client.post(
                f"/questions/by_group/{group['id']}",
                json={
                    "question": text,
                    "annotations": [
                        {"passage": first, "term": first, "start": 0, "end": len(first)},
                        {"passage": second, "term": second, "start": len(first) + 1, "end": len(text)},
                    ],
                },
                headers=admin_header,
            )
            assert response.status_code == HTTP_201_CREATED, response.text
            question_id = response.json()["id"]

            # Text inserted before both spans shifts them.
            revision = _revise(client, admin_header, question_id, f"Neu {text}")
            assert _spans(revision) == sorted([(first, 4, 4 + len(first)), (second, 5 + len(first), 4 + len(text))])

            # Replacing one annotated passage keeps only the other annotation.
            revision = _revise(client, admin_header, question_id, f"Neu {first} Bittsteller")
            assert _spans(revision) == [(first, 4, 4 + len(first))]

            # Once no annotation matches, the revision starts without a snapshot.
            revision = _revise(client, admin_header, question_id, "Ganz andere Frage")
            assert revision["annotationVersions"] == []
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_revision_stores_annotations_moved_by_the_editor(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        admin_header = login(client)
        project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])
        first, second = unique_text("Pfründe"), unique_text("Petent")
        text = f"{first} {second}"

        try:
            response = client.post(
                f"/questions/by_group/{group['id']}",
                json={
                    "question": text,
                    "annotations": [
                        {"passage": first, "term": first, "start": 0, "end": len(first)},
                        {"passage": second, "term": second, "start": len(first) + 1, "end": len(text)},
                    ],
                },
                headers=admin_header,
            )
            assert response.status_code == HTTP_201_CREATED, response.text
            question_id = response.json()["id"]

            # Swapping both words: the editor followed the edits, a text diff could only keep one span.
            swapped = f"{second} {first}"
            moved = [
                {"passage": second, "term": second, "start": 0, "end": len(second)},
                {"passage": first, "term": first, "start": len(second) + 1, "end": len(swapped)},
            ]
            response = client.put(
                f"/questions/{question_id}", json={"question": swapped, "annotations": moved}, headers=admin_header
            )
            assert response.status_code == HTTP_200_OK, response.text
            revision = max(response.json()["revisions"], key=lambda item: item["versionNumber"])
            assert _spans(revision) == sorted([(second, 0, len(second)), (first, len(second) + 1, len(swapped))])
            assert revision["annotationVersions"][0]["retainedFromAnnotationVersionId"]

            # A span that does not match the new text is rejected and nothing is saved.
            response = client.put(
                f"/questions/{question_id}",
                json={"question": f"Neu {swapped}", "annotations": moved},
                headers=admin_header,
            )
            assert response.status_code == 400, response.text
            response = client.get(f"/questions/{question_id}", headers=admin_header)
            assert response.json()["question"] == swapped

            # Submitting no annotations for an annotated question starts the revision without a snapshot.
            revision = _revise_with(client, admin_header, question_id, {"question": "Ganz andere Frage", "annotations": []})
            assert revision["annotationVersions"] == []
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
