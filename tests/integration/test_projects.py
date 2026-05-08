from httpx import Headers
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_204_NO_CONTENT
from litestar.testing import TestClient

from ._fixtures import (
    create_project,
    test_client,
    admin_header,
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
