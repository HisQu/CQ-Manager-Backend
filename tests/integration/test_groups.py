from httpx import Headers
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT, HTTP_401_UNAUTHORIZED
from litestar.testing import TestClient

from ._fixtures import (
    MANAGER_EMAIL,
    TEST_PASSWORD,
    admin_header,
    create_group,
    create_project,
    create_question,
    login,
    register_user,
    test_client,
    unique_text,
    verify_user,
)  # pyright: ignore


def test_get_all_groups(test_client: TestClient[Litestar], admin_header: Headers) -> None:
    with test_client as client:
        response = client.get("/groups", headers=admin_header)
        assert response.status_code == HTTP_200_OK, response.text
        assert isinstance(response.json(), list)


def test_created_group_is_visible_in_my_groups(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])

        try:
            assert group["noMembers"] == 1
            assert group["project"]["id"] == project["id"]

            my_groups = client.get("/groups/my_groups", headers=admin_header)
            assert my_groups.status_code == HTTP_200_OK, my_groups.text
            assert group["id"] in {group["id"] for group in my_groups.json()}
        finally:
            project_delete_response = client.delete(
                f"/projects/{project['id']}",
                headers=admin_header,
            )
            assert project_delete_response.status_code == HTTP_204_NO_CONTENT


def test_non_project_manager_cannot_create_group(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        user = register_user(client)
        verify_user(client, admin_header, user["email"])
        user_header = login(client, user["email"], TEST_PASSWORD)
        project = create_project(client, admin_header)

        try:
            response = client.post(
                f"/groups/{project['id']}",
                json={"name": unique_text("Blocked Group")},
                headers=user_header,
            )

            assert response.status_code == HTTP_401_UNAUTHORIZED, response.text
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
            client.delete(f"/users/{user['email']}", headers=admin_header)


def test_system_admin_can_create_group_without_project_manager_role(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header, managers=[MANAGER_EMAIL])

        try:
            response = client.post(
                f"/groups/{project['id']}",
                json={"name": unique_text("Admin Created Group")},
                headers=admin_header,
            )

            assert response.status_code == HTTP_201_CREATED, response.text
            assert response.json()["project"]["id"] == project["id"]
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_group_comment_can_be_created_and_updated(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header)
        comment = "\n".join(
            [
                unique_text("Initial group comment"),
                "This is deliberately a longer free-text field.",
                "It should preserve line breaks and enough content for notes.",
            ]
        )
        updated_comment = "\n\n".join([comment, unique_text("Follow-up comment")])
        group = create_group(client, admin_header, project["id"], comment=comment)

        try:
            assert group["comment"] == comment

            detail_response = client.get(
                f"/groups/{project['id']}/{group['id']}",
                headers=admin_header,
            )
            assert detail_response.status_code == HTTP_200_OK, detail_response.text
            assert detail_response.json()["comment"] == comment

            update_response = client.put(
                f"/groups/{project['id']}/{group['id']}",
                json={"comment": updated_comment},
                headers=admin_header,
            )
            assert update_response.status_code == HTTP_200_OK, update_response.text
            assert update_response.json()["comment"] == updated_comment

            project_response = client.get(f"/projects/{project['id']}", headers=admin_header)
            assert project_response.status_code == HTTP_200_OK, project_response.text
            project_group = next(
                group
                for group in project_response.json()["groups"]
                if group["id"] == update_response.json()["id"]
            )
            assert project_group["comment"] == updated_comment

            clear_response = client.put(
                f"/groups/{project['id']}/{group['id']}",
                json={"comment": None},
                headers=admin_header,
            )
            assert clear_response.status_code == HTTP_200_OK, clear_response.text
            assert clear_response.json()["comment"] is None
        finally:
            delete_response = client.delete(f"/projects/{project['id']}", headers=admin_header)
            assert delete_response.status_code == HTTP_204_NO_CONTENT


def test_add_existing_user_to_group(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        user = register_user(client)
        verify_user(client, admin_header, user["email"])
        project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])

        try:
            response = client.put(
                f"/groups/{project['id']}/{group['id']}/members/add",
                json={"emails": [user["email"]]},
                headers=admin_header,
            )
            assert response.status_code == HTTP_200_OK, response.text

            group_response = client.get(
                f"/groups/{project['id']}/{group['id']}",
                headers=admin_header,
            )
            assert group_response.status_code == HTTP_200_OK, group_response.text
            assert user["email"] in {member["email"] for member in group_response.json()["members"]}
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
            client.delete(f"/users/{user['email']}", headers=admin_header)


def test_group_member_permission_headers_do_not_grant_project_roles(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        user = register_user(client)
        verify_user(client, admin_header, user["email"])
        user_header = login(client, user["email"], TEST_PASSWORD)
        project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])

        try:
            add_response = client.put(
                f"/groups/{project['id']}/{group['id']}/members/add",
                json={"emails": [user["email"]]},
                headers=admin_header,
            )
            assert add_response.status_code == HTTP_200_OK, add_response.text

            response = client.get(
                f"/groups/{project['id']}/{group['id']}",
                headers=user_header,
            )
            assert response.status_code == HTTP_200_OK, response.text
            assert response.headers["Permissions-Group-Member"] == "True"
            assert response.headers["Permissions-Project-Member"] == "True"
            assert response.headers["Permissions-Project-Engineer"] == "False"
            assert response.headers["Permissions-Project-Manager"] == "False"
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
            client.delete(f"/users/{user['email']}", headers=admin_header)


def test_project_manager_can_update_group_without_group_membership(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        manager = register_user(client)
        verify_user(client, admin_header, manager["email"])
        manager_header = login(client, manager["email"], TEST_PASSWORD)
        project = create_project(
            client,
            admin_header,
            managers=[manager["email"], "admin@uni-jena.de"],
        )
        group = create_group(client, admin_header, project["id"])
        updated_name = unique_text("Updated Group")

        try:
            group_response = client.get(
                f"/groups/{project['id']}/{group['id']}",
                headers=manager_header,
            )
            assert group_response.status_code == HTTP_200_OK, group_response.text
            assert manager["email"] not in {member["email"] for member in group_response.json()["members"]}

            response = client.put(
                f"/groups/{project['id']}/{group['id']}",
                json={"name": updated_name},
                headers=manager_header,
            )
            assert response.status_code == HTTP_200_OK, response.text
            assert response.json()["name"] == updated_name
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
            client.delete(f"/users/{manager['email']}", headers=admin_header)


def test_deleting_project_deletes_groups(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])

        try:
            delete_response = client.delete(f"/projects/{project['id']}", headers=admin_header)
            assert delete_response.status_code == HTTP_204_NO_CONTENT

            direct_group = client.get(f"/groups/direct/{group['id']}", headers=admin_header)
            assert direct_group.status_code == 404, direct_group.text

            groups_response = client.get("/groups", headers=admin_header)
            assert groups_response.status_code == HTTP_200_OK, groups_response.text
            assert group["id"] not in {group["id"] for group in groups_response.json()}
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_deleting_project_deletes_group_questions(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header)
        group = create_group(client, admin_header, project["id"])
        question = create_question(client, admin_header, group["id"])

        annotation_response = client.put(
            f"/terms/add/{question['id']}",
            json={
                "annotations": [
                    {
                        "term": "Cascade term",
                        "passage": "Cascade passage",
                    }
                ]
            },
            headers=admin_header,
        )
        assert annotation_response.status_code == HTTP_200_OK, annotation_response.text

        try:
            delete_response = client.delete(f"/projects/{project['id']}", headers=admin_header)
            assert delete_response.status_code == HTTP_204_NO_CONTENT

            question_detail = client.get(
                f"/questions/{group['id']}/{question['id']}",
                headers=admin_header,
            )
            assert question_detail.status_code == 404, question_detail.text

            project_questions = client.get(
                f"/questions/by_project/{project['id']}",
                headers=admin_header,
            )
            assert project_questions.status_code == HTTP_200_OK, project_questions.text
            assert question["id"] not in {question["id"] for question in project_questions.json()}

            project_terms = client.get(
                f"/terms/project/{project['id']}",
                headers=admin_header,
            )
            assert project_terms.status_code == HTTP_200_OK, project_terms.text
            assert project_terms.json() == []
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
