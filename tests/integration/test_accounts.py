from uuid import uuid4

from httpx import Headers
from litestar import Litestar
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_409_CONFLICT,
)
from litestar.testing import TestClient

from ._fixtures import (
    TEST_PASSWORD,
    admin_header,
    create_group,
    create_project,
    create_question,
    login,
    register_user,
    test_client,
    verify_user,
)  # pyright: ignore


def _unique_email() -> str:
    return f"user-{uuid4().hex}@example.com"


def test_user_lifecycle(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    email = _unique_email()
    new_password = "12345678HalloNeu"

    with test_client as client:
        try:
            data = {
                "email": email,
                "name": email,
                "password": "12345",
            }
            response = client.post("/users/register", json=data)
            assert response.status_code == HTTP_400_BAD_REQUEST

            data["password"] = "12345678"
            response = client.post("/users/register", json=data)
            assert response.status_code == HTTP_400_BAD_REQUEST

            data["password"] = TEST_PASSWORD
            response = client.post("/users/register", json=data)
            assert response.status_code == HTTP_201_CREATED
            assert response.json()["email"] == email

            response = client.put(f"/users/verify/{email}")
            assert response.status_code == HTTP_401_UNAUTHORIZED

            response = client.put(f"/users/verify/{email}", headers=admin_header)
            assert response.status_code == HTTP_200_OK

            user_header = login(client, email, TEST_PASSWORD)

            response = client.put(
                "/users/password",
                json={
                    "current_password": TEST_PASSWORD,
                    "new_password": new_password,
                },
            )
            assert response.status_code == HTTP_401_UNAUTHORIZED

            response = client.put(
                "/users/password",
                json={
                    "current_password": TEST_PASSWORD,
                    "new_password": new_password,
                },
                headers=user_header,
            )
            assert response.status_code == HTTP_204_NO_CONTENT

            response = client.post(
                "/users/login",
                json={"email": email, "password": TEST_PASSWORD},
            )
            assert response.status_code == HTTP_401_UNAUTHORIZED

            user_header = login(client, email, new_password)

            response = client.put(f"/users/{email}", json={"name": f"{email}-updated"})
            assert response.status_code == HTTP_401_UNAUTHORIZED

            response = client.put(
                f"/users/{email}",
                json={"name": f"{email}-updated"},
                headers=admin_header,
            )
            assert response.status_code == HTTP_200_OK
            assert response.json()["name"] == f"{email}-updated"

            response = client.get(f"/users/{email}")
            assert response.status_code == HTTP_401_UNAUTHORIZED

            response = client.get(f"/users/{email}", headers=user_header)
            assert response.status_code == HTTP_200_OK
            assert response.json()["name"] == f"{email}-updated"

            response = client.get("/users")
            assert response.status_code == HTTP_401_UNAUTHORIZED

            response = client.get("/users", headers=user_header)
            assert response.status_code == HTTP_200_OK

            response = client.delete(f"/users/{email}")
            assert response.status_code == HTTP_401_UNAUTHORIZED

            response = client.delete(f"/users/{email}", headers=admin_header)
            assert response.status_code == HTTP_204_NO_CONTENT
        finally:
            client.delete(f"/users/{email}", headers=admin_header)


def test_update_user_allows_unchanged_unique_fields(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    email = _unique_email()
    new_email = _unique_email()
    updated_name = f"{email}-updated"

    with test_client as client:
        try:
            register_user(client, email=email)
            verify_user(client, admin_header, email)

            response = client.put(
                f"/users/{email}",
                json={
                    "email": email,
                    "name": updated_name,
                    "is_system_admin": False,
                    "is_verified": False,
                },
                headers=admin_header,
            )
            assert response.status_code == HTTP_200_OK
            assert response.json()["email"] == email
            assert response.json()["name"] == updated_name
            assert response.json()["is_system_admin"] is False
            assert response.json()["is_verified"] is False

            response = client.put(
                f"/users/{email}",
                json={
                    "email": new_email,
                    "is_system_admin": True,
                    "is_verified": True,
                },
                headers=admin_header,
            )
            assert response.status_code == HTTP_200_OK
            assert response.json()["email"] == new_email
            assert response.json()["is_system_admin"] is True
            assert response.json()["is_verified"] is True

            response = client.put(
                f"/users/{new_email}",
                json={"is_system_admin": False},
                headers=admin_header,
            )
            assert response.status_code == HTTP_200_OK
            assert response.json()["is_system_admin"] is False
        finally:
            client.delete(f"/users/{new_email}", headers=admin_header)
            client.delete(f"/users/{email}", headers=admin_header)


def test_delete_user_referenced_by_entities(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    email = _unique_email()

    with test_client as client:
        register_user(client, email=email)
        verify_user(client, admin_header, email)
        user_header = login(client, email, TEST_PASSWORD)
        project = create_project(
            client,
            admin_header,
            managers=[email],
            engineers=[email],
        )
        group = create_group(client, user_header, project["id"])
        create_question(client, user_header, group["id"])

        try:
            response = client.delete(f"/users/{email}", headers=admin_header)
            assert response.status_code == HTTP_409_CONFLICT
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
            client.delete(f"/users/{email}", headers=admin_header)
