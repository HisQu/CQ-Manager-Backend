from httpx import Headers
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_204_NO_CONTENT, HTTP_409_CONFLICT
from litestar.testing import TestClient

from ._fixtures import (
    TEST_PASSWORD,
    create_project,
    create_group,
    create_question,
    login,
    register_user,
    test_client,
    admin_header,
    verify_user,
)  # pyright: ignore


def test_get_all(test_client: TestClient[Litestar], admin_header: Headers) -> None:
    with test_client as client:
        response = client.get("/projects", headers=admin_header)
        assert response.status_code == HTTP_200_OK


def test_created_project_is_listed(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header)

        try:
            response = client.get("/projects", headers=admin_header)
            assert response.status_code == HTTP_200_OK
            assert project["id"] in {project["id"] for project in response.json()}
        finally:
            delete_response = client.delete(f"/projects/{project['id']}", headers=admin_header)
            assert delete_response.status_code == HTTP_204_NO_CONTENT


def test_get_project_without_groups(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        project = create_project(client, admin_header)

        try:
            detail_response = client.get(f"/projects/{project['id']}", headers=admin_header)
            assert detail_response.status_code == HTTP_200_OK, detail_response.text
            project_detail = detail_response.json()
            assert project_detail["groups"] == []
            assert project_detail["noGroups"] == 0
        finally:
            delete_response = client.delete(f"/projects/{project['id']}", headers=admin_header)
            assert delete_response.status_code == HTTP_204_NO_CONTENT


def test_delete_project_with_user_created_cq(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        user = register_user(client)
        verify_user(client, admin_header, user["email"])
        user_header = login(client, user["email"], TEST_PASSWORD)
        project = create_project(
            client,
            admin_header,
            managers=[user["email"]],
            engineers=[user["email"]],
        )
        group = create_group(client, user_header, project["id"])
        question = create_question(client, user_header, group["id"])

        try:
            delete_response = client.delete(f"/projects/{project['id']}", headers=admin_header)
            assert delete_response.status_code == HTTP_204_NO_CONTENT

            question_detail = client.get(
                f"/questions/{group['id']}/{question['id']}",
                headers=user_header,
            )
            assert question_detail.status_code == 404, question_detail.text

            user_delete_response = client.delete(f"/users/{user['email']}", headers=admin_header)
            assert user_delete_response.status_code == HTTP_204_NO_CONTENT
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
            client.delete(f"/users/{user['email']}", headers=admin_header)


def test_delete_project_with_user_created_cq_keeps_unrelated_user_references(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        user = register_user(client)
        verify_user(client, admin_header, user["email"])
        user_header = login(client, user["email"], TEST_PASSWORD)
        cq_project = create_project(
            client,
            admin_header,
            managers=[user["email"]],
            engineers=[user["email"]],
        )
        cq_group = create_group(client, user_header, cq_project["id"])
        create_question(client, user_header, cq_group["id"])
        other_project = create_project(
            client,
            admin_header,
            managers=[user["email"]],
            engineers=[user["email"]],
        )
        other_group = create_group(client, user_header, other_project["id"])
        create_question(client, user_header, other_group["id"])

        try:
            delete_response = client.delete(f"/projects/{cq_project['id']}", headers=admin_header)
            assert delete_response.status_code == HTTP_204_NO_CONTENT

            blocked_user_delete = client.delete(f"/users/{user['email']}", headers=admin_header)
            assert blocked_user_delete.status_code == HTTP_409_CONFLICT

            other_project_delete = client.delete(f"/projects/{other_project['id']}", headers=admin_header)
            assert other_project_delete.status_code == HTTP_204_NO_CONTENT

            user_delete_response = client.delete(f"/users/{user['email']}", headers=admin_header)
            assert user_delete_response.status_code == HTTP_204_NO_CONTENT
        finally:
            client.delete(f"/projects/{cq_project['id']}", headers=admin_header)
            client.delete(f"/projects/{other_project['id']}", headers=admin_header)
            client.delete(f"/users/{user['email']}", headers=admin_header)
