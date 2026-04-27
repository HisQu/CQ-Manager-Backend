import sys

import pytest
from litestar import Litestar
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)
from litestar.testing import TestClient

sys.path.append("src/app/")


from app import app


@pytest.fixture(scope="module")
def test_client() -> TestClient[Litestar]:
    return TestClient(app=app)  # type: ignore


new_user_id = None
new_user_header = None
admin_header = None


def test_register_new_user(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        data = {
            "email": "dominik@uni-jena.de",
            "name": "dominik",
            "password": "12345",
        }

        response = client.post("/users/register", json=data)
        assert response.status_code == HTTP_400_BAD_REQUEST

        data["password"] = "12345678"
        response = client.post("/users/register", json=data)
        assert response.status_code == HTTP_400_BAD_REQUEST

        data["password"] = "12345678Hallo"
        response = client.post("/users/register", json=data)
        assert response.status_code == HTTP_201_CREATED
        assert response.json().get("id", None) is not None

        global new_user_id
        new_user_id = response.json()["id"]


def test_login_admin(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        data = {
            "email": "admin@uni-jena.de",
            "password": "HalloWelt123",
        }
        response = client.post(f"/users/login", json=data)
        assert response.status_code == HTTP_201_CREATED
        assert response.headers.get("Authorization", None) is not None
        global admin_header
        admin_header = response.headers


def test_verify_user_wo_admin(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        response = client.put(f"/users/verify/{new_user_id}")
        assert response.status_code == HTTP_401_UNAUTHORIZED


def test_verify_user_w_admin(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        response = client.put(f"/users/verify/{new_user_id}", headers=admin_header)
        assert response.status_code == HTTP_200_OK


def test_login_new_user(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        data = {
            "email": "dominik@uni-jena.de",
            "password": "12345678Hallo",
        }
        response = client.post(f"/users/login", json=data)
        assert response.status_code == HTTP_201_CREATED
        assert response.headers.get("Authorization", None) is not None
        global new_user_header
        new_user_header = response.headers


def test_change_password_wo_login(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        response = client.put(
            "/users/password",
            json={
                "current_password": "12345678Hallo",
                "new_password": "12345678HalloNeu",
            },
        )
        assert response.status_code == HTTP_401_UNAUTHORIZED


def test_change_password_w_login(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        response = client.put(
            "/users/password",
            json={
                "current_password": "12345678Hallo",
                "new_password": "12345678HalloNeu",
            },
            headers=new_user_header,
        )
        assert response.status_code == HTTP_204_NO_CONTENT


def test_login_new_user_with_old_password(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        response = client.post(
            "/users/login",
            json={"email": "dominik@uni-jena.de", "password": "12345678Hallo"},
        )
        assert response.status_code == HTTP_401_UNAUTHORIZED


def test_login_new_user_with_new_password(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        response = client.post(
            "/users/login",
            json={"email": "dominik@uni-jena.de", "password": "12345678HalloNeu"},
        )
        assert response.status_code == HTTP_201_CREATED
        assert response.headers.get("Authorization", None) is not None


def test_update_user_wo_admin(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        response = client.put(f"/users/{new_user_id}", json={"name": "dominik_neu"})
        assert response.status_code == HTTP_401_UNAUTHORIZED


def test_update_user_w_admin(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        response = client.put(
            f"/users/{new_user_id}", json={"name": "dominik_neu"}, headers=admin_header
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["name"] == "dominik_neu"


def test_get_user_wo_login(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        response = client.get(f"/users/{new_user_id}")
        assert response.status_code == HTTP_401_UNAUTHORIZED


def test_get_user_w_login(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        response = client.get(f"/users/{new_user_id}", headers=new_user_header)
        assert response.status_code == HTTP_200_OK
        assert response.json()["name"] == "dominik_neu"


def test_get_users_wo_login(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        response = client.get(f"/users")
        assert response.status_code == HTTP_401_UNAUTHORIZED


def test_get_users_w_login(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        response = client.get(f"/users", headers=new_user_header)
        assert response.status_code == HTTP_200_OK


def test_delete_users_wo_admin(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        response = client.delete(f"/users/{new_user_id}")
        assert response.status_code == HTTP_401_UNAUTHORIZED


def test_delete_users_w_admin(test_client: TestClient[Litestar]) -> None:
    with test_client as client:
        response = client.delete(f"/users/{new_user_id}", headers=admin_header)
        assert response.status_code == HTTP_204_NO_CONTENT
