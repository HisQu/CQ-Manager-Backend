from httpx import Headers
from litestar import Litestar
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)
from litestar.testing import TestClient

from ._fixtures import (
    ENGINEER_EMAIL,
    TEST_PASSWORD,
    admin_header,
    create_consolidation,
    create_group,
    create_project,
    create_question,
    login,
    register_user,
    test_client,
    unique_text,
    verify_user,
)


def create_tag(client: TestClient[Litestar], headers: Headers, project_id: str, name: str) -> dict:
    response = client.post(f"/tags/{project_id}", json={"name": name}, headers=headers)
    assert response.status_code == HTTP_201_CREATED, response.text
    return response.json()


def set_question_tags(
    client: TestClient[Litestar],
    headers: Headers,
    project_id: str,
    question_id: str,
    tag_ids: list[str],
) -> dict:
    response = client.put(
        f"/tags/{project_id}/questions/{question_id}",
        json={"tagIds": tag_ids},
        headers=headers,
    )
    assert response.status_code == HTTP_200_OK, response.text
    return response.json()


def add_group_member(client: TestClient[Litestar], admin_header: Headers, project_id: str, group_id: str) -> tuple[dict, Headers]:
    user = register_user(client)
    verify_user(client, admin_header, user["email"])
    response = client.put(
        f"/groups/{project_id}/{group_id}/members/add",
        json={"emails": [user["email"]]},
        headers=admin_header,
    )
    assert response.status_code == HTTP_200_OK, response.text
    return user, login(client, user["email"], TEST_PASSWORD)


def test_tag_crud_names_are_normalized_unique_and_sorted(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header)

        try:
            beta = create_tag(client, admin_header, project["id"], "  beta   tag ")
            assert beta["name"] == "beta tag"
            assert beta["projectId"] == project["id"]
            assert beta["noQuestions"] == 0
            create_tag(client, admin_header, project["id"], "Alpha")

            duplicate = client.post(f"/tags/{project['id']}", json={"name": "BETA TAG"}, headers=admin_header)
            assert duplicate.status_code == HTTP_400_BAD_REQUEST, duplicate.text

            empty = client.post(f"/tags/{project['id']}", json={"name": "   "}, headers=admin_header)
            assert empty.status_code == HTTP_400_BAD_REQUEST, empty.text

            too_long = client.post(f"/tags/{project['id']}", json={"name": "x" * 51}, headers=admin_header)
            assert too_long.status_code == HTTP_400_BAD_REQUEST, too_long.text

            listed = client.get(f"/tags/{project['id']}", headers=admin_header)
            assert listed.status_code == HTTP_200_OK, listed.text
            assert [tag["name"] for tag in listed.json()] == ["Alpha", "beta tag"]

            renamed = client.put(f"/tags/{project['id']}/{beta['id']}", json={"name": "Gamma"}, headers=admin_header)
            assert renamed.status_code == HTTP_200_OK, renamed.text
            assert renamed.json()["name"] == "Gamma"

            rename_to_existing = client.put(
                f"/tags/{project['id']}/{beta['id']}", json={"name": "alpha"}, headers=admin_header
            )
            assert rename_to_existing.status_code == HTTP_400_BAD_REQUEST, rename_to_existing.text

            deleted = client.delete(f"/tags/{project['id']}/{beta['id']}", headers=admin_header)
            assert deleted.status_code == HTTP_204_NO_CONTENT, deleted.text
            listed = client.get(f"/tags/{project['id']}", headers=admin_header)
            assert [tag["name"] for tag in listed.json()] == ["Alpha"]
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_tags_are_project_specific(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header)
        other_project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])
        question = create_question(client, admin_header, group["id"])

        try:
            create_tag(client, admin_header, project["id"], "Shared name")
            other_tag = create_tag(client, admin_header, other_project["id"], "Shared name")

            assert [tag["name"] for tag in client.get(f"/tags/{project['id']}", headers=admin_header).json()] == [
                "Shared name"
            ]

            foreign_tag = client.put(
                f"/tags/{project['id']}/questions/{question['id']}",
                json={"tagIds": [other_tag["id"]]},
                headers=admin_header,
            )
            assert foreign_tag.status_code == HTTP_400_BAD_REQUEST, foreign_tag.text

            foreign_question = client.put(
                f"/tags/{other_project['id']}/questions/{question['id']}",
                json={"tagIds": [other_tag["id"]]},
                headers=admin_header,
            )
            assert foreign_question.status_code == HTTP_404_NOT_FOUND, foreign_question.text

            foreign_rename = client.put(
                f"/tags/{project['id']}/{other_tag['id']}", json={"name": "Hijacked"}, headers=admin_header
            )
            assert foreign_rename.status_code == HTTP_404_NOT_FOUND, foreign_rename.text
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
            client.delete(f"/projects/{other_project['id']}", headers=admin_header)


def test_question_tags_are_set_returned_counted_and_removed_with_tag(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])
        question = create_question(client, admin_header, group["id"])
        other_question = create_question(client, admin_header, group["id"])

        try:
            urgent = create_tag(client, admin_header, project["id"], "urgent")
            archive = create_tag(client, admin_header, project["id"], "Archive")

            overview = set_question_tags(
                client, admin_header, project["id"], question["id"], [urgent["id"], archive["id"], urgent["id"]]
            )
            assert [tag["name"] for tag in overview["tags"]] == ["Archive", "urgent"]
            set_question_tags(client, admin_header, project["id"], other_question["id"], [urgent["id"]])

            detail = client.get(f"/questions/{question['id']}", headers=admin_header).json()
            assert {tag["id"] for tag in detail["tags"]} == {urgent["id"], archive["id"]}

            for url in (
                f"/questions/by_project/{project['id']}",
                f"/questions/by_project/{project['id']}/unified",
                f"/questions/by_group/{group['id']}",
                f"/questions/by_group/{group['id']}/unified",
            ):
                listed = {item["id"]: item for item in client.get(url, headers=admin_header).json()}
                assert [tag["name"] for tag in listed[question["id"]]["tags"]] == ["Archive", "urgent"], url

            counts = {tag["name"]: tag["noQuestions"] for tag in client.get(f"/tags/{project['id']}", headers=admin_header).json()}
            assert counts == {"Archive": 1, "urgent": 2}

            assert client.delete(f"/tags/{project['id']}/{urgent['id']}", headers=admin_header).status_code == HTTP_204_NO_CONTENT
            detail = client.get(f"/questions/{question['id']}", headers=admin_header).json()
            assert [tag["name"] for tag in detail["tags"]] == ["Archive"]

            cleared = set_question_tags(client, admin_header, project["id"], question["id"], [])
            assert cleared["tags"] == []
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_question_can_be_created_with_tags(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header)
        other_project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])

        try:
            tag = create_tag(client, admin_header, project["id"], "From creation")
            response = client.post(
                f"/questions/by_group/{group['id']}",
                json={"question": unique_text("Tagged question?"), "tagIds": [tag["id"]]},
                headers=admin_header,
            )
            assert response.status_code == HTTP_201_CREATED, response.text
            assert [item["name"] for item in response.json()["tags"]] == ["From creation"]

            foreign_tag = create_tag(client, admin_header, other_project["id"], "Foreign")
            response = client.post(
                f"/questions/by_group/{group['id']}",
                json={"question": unique_text("Foreign tag?"), "tagIds": [foreign_tag["id"]]},
                headers=admin_header,
            )
            assert response.status_code == HTTP_400_BAD_REQUEST, response.text
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
            client.delete(f"/projects/{other_project['id']}", headers=admin_header)


def test_unified_consolidation_entry_carries_result_question_tags(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header, engineers=[ENGINEER_EMAIL])
        group = create_group(client, admin_header, project["id"])
        source_a = create_question(client, admin_header, group["id"])
        source_b = create_question(client, admin_header, group["id"])
        target = create_question(client, admin_header, group["id"])

        try:
            tag = create_tag(client, admin_header, project["id"], "Consolidated")
            set_question_tags(client, admin_header, project["id"], target["id"], [tag["id"]])
            create_consolidation(
                client,
                admin_header,
                project["id"],
                question_ids=[source_a["id"], source_b["id"]],
                target_question_id=target["id"],
            )

            unified = client.get(f"/questions/by_project/{project['id']}/unified", headers=admin_header).json()
            entry = next(item for item in unified if item["unifiedEntryKind"] == "consolidation_result")
            assert [item["name"] for item in entry["tags"]] == ["Consolidated"]
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_tag_permissions(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header, engineers=[ENGINEER_EMAIL])
        other_project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])
        question = create_question(client, admin_header, group["id"])
        member, member_header = add_group_member(client, admin_header, project["id"], group["id"])
        engineer_header = login(client, ENGINEER_EMAIL)

        try:
            # Group members may create tags and tag questions ...
            tag = create_tag(client, member_header, project["id"], "Member tag")
            set_question_tags(client, member_header, project["id"], question["id"], [tag["id"]])

            # ... but renaming or deleting a tag is reserved to managers and engineers.
            rename = client.put(f"/tags/{project['id']}/{tag['id']}", json={"name": "Renamed"}, headers=member_header)
            assert rename.status_code == HTTP_401_UNAUTHORIZED, rename.text
            delete = client.delete(f"/tags/{project['id']}/{tag['id']}", headers=member_header)
            assert delete.status_code == HTTP_401_UNAUTHORIZED, delete.text

            rename = client.put(f"/tags/{project['id']}/{tag['id']}", json={"name": "Renamed"}, headers=engineer_header)
            assert rename.status_code == HTTP_200_OK, rename.text
            assert rename.json()["noQuestions"] == 1

            # Outsiders may not create tags in a project they do not participate in.
            outsider = client.post(f"/tags/{other_project['id']}", json={"name": "Nope"}, headers=member_header)
            assert outsider.status_code == HTTP_401_UNAUTHORIZED, outsider.text
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
            client.delete(f"/projects/{other_project['id']}", headers=admin_header)
            client.delete(f"/users/{member['email']}", headers=admin_header)
