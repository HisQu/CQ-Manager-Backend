from httpx import Headers
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_204_NO_CONTENT, HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND
from litestar.testing import TestClient

from ._fixtures import (
    admin_header,
    create_group,
    create_project,
    create_question,
    test_client,
)
from .test_tags import add_group_member, create_tag, set_question_tags
from .test_topics import create_topic


def get_history(client: TestClient[Litestar], headers: Headers, question_id: str) -> list[dict]:
    response = client.get(f"/questions/{question_id}/history", headers=headers)
    assert response.status_code == HTTP_200_OK, response.text
    return response.json()


def summarize(events: list[dict]) -> list[tuple]:
    return [
        (event["eventType"], event["versionNumber"], event["tagName"] or event["catalogueIdentifier"])
        for event in events
    ]


def test_history_records_creation_revisions_tags_and_catalogue(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])

        try:
            urgent = create_tag(client, admin_header, project["id"], "urgent")
            archive = create_tag(client, admin_header, project["id"], "archive")
            topic = create_topic(client, admin_header, project["id"], identifier="A")

            response = client.post(
                f"/questions/by_group/{group['id']}",
                json={"question": "Who petitioned?", "tagIds": [urgent["id"]]},
                headers=admin_header,
            )
            question = response.json()

            # Changing the comment is no revision, changing the SPARQL query is.
            client.put(f"/questions/{question['id']}", json={"comment": "note"}, headers=admin_header)
            detail = client.put(
                f"/questions/{question['id']}", json={"comment": "note", "sparqlQuery": "SELECT ?p"}, headers=admin_header
            ).json()
            assert detail["versionNumber"] == 2
            assert detail["comment"] == "note"
            assert [(v["versionNumber"], v["questionString"], v["sparqlQuery"]) for v in detail["versions"]] == [
                (1, "Who petitioned?", None)
            ]

            set_question_tags(client, admin_header, project["id"], question["id"], [archive["id"]])
            client.post(f"/topics/{project['id']}/{topic['id']}/questions/{question['id']}", headers=admin_header)
            client.delete(f"/tags/{project['id']}/{archive['id']}", headers=admin_header)

            events = get_history(client, admin_header, question["id"])
            assert summarize(events) == [
                ("created", 1, None),
                ("tag_added", 1, "urgent"),
                ("catalogue_assigned", 1, "#.1"),
                ("revised", 2, None),
                ("tag_removed", 2, "urgent"),
                ("tag_added", 2, "archive"),
                ("catalogue_assigned", 2, "A.1"),
                ("tag_removed", 2, "archive"),
            ]
            assert all(event["actor"]["email"] == "admin@uni-jena.de" for event in events)
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_deleted_questions_are_hidden_but_kept_for_system_admins(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])
        _, member_header = add_group_member(client, admin_header, project["id"], group["id"])
        question = create_question(client, member_header, group["id"])
        kept = create_question(client, member_header, group["id"])

        try:
            tag = create_tag(client, admin_header, project["id"], "urgent")
            set_question_tags(client, member_header, project["id"], question["id"], [tag["id"]])

            response = client.delete(f"/questions/{question['id']}", headers=member_header)
            assert response.status_code == HTTP_204_NO_CONTENT, response.text

            for url in (
                f"/questions/by_project/{project['id']}",
                f"/questions/by_project/{project['id']}/unified",
                f"/questions/by_group/{group['id']}",
            ):
                ids = {item["id"] for item in client.get(url, headers=admin_header).json()}
                assert ids == {kept["id"]}, url
            counts = {t["name"]: t["noQuestions"] for t in client.get(f"/tags/{project['id']}", headers=admin_header).json()}
            assert counts == {"urgent": 0}

            assert client.get(f"/questions/{question['id']}", headers=member_header).status_code == HTTP_404_NOT_FOUND
            history = client.get(f"/questions/{question['id']}/history", headers=member_header)
            assert history.status_code == HTTP_404_NOT_FOUND

            detail = client.get(f"/questions/{question['id']}", headers=admin_header).json()
            assert detail["deletedAt"] is not None
            assert detail["cqCatalogueIdentifier"] == "#.1"
            assert [t["name"] for t in detail["tags"]] == ["urgent"]
            assert summarize(get_history(client, admin_header, question["id"]))[-1] == ("deleted", 1, None)

            deleted_url = f"/questions/by_project/{project['id']}/deleted"
            assert client.get(deleted_url, headers=member_header).status_code == HTTP_401_UNAUTHORIZED
            deleted = client.get(deleted_url, headers=admin_header).json()
            assert [(item["id"], item["deletedAt"] is not None) for item in deleted] == [(question["id"], True)]

            # The identifier of a deleted question is not handed out again.
            assert create_question(client, member_header, group["id"])["cqCatalogueIdentifier"] == "#.3"
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
