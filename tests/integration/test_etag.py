from httpx import Headers
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_304_NOT_MODIFIED
from litestar.testing import TestClient

from ._fixtures import (
    ENGINEER_EMAIL,
    admin_header,
    create_group,
    create_project,
    create_question,
    login,
    test_client,
)


def test_question_list_is_answered_with_not_modified_until_it_changes(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        admin_header = login(client)
        engineer_header = login(client, ENGINEER_EMAIL)
        project = create_project(client, admin_header, engineers=[ENGINEER_EMAIL])
        group = create_group(client, admin_header, project["id"])
        question = create_question(client, admin_header, group["id"])
        path = f"/questions/by_project/{project['id']}/unified"

        try:
            response = client.get(path, headers=admin_header)
            assert response.status_code == HTTP_200_OK, response.text
            etag = response.headers["ETag"]
            assert response.headers["Cache-Control"] == "private, no-cache"

            unchanged = client.get(path, headers={**admin_header, "If-None-Match": etag})
            assert unchanged.status_code == HTTP_304_NOT_MODIFIED
            assert unchanged.content == b""
            assert unchanged.headers["ETag"] == etag

            # Weak and listed tags match as well.
            listed = client.get(path, headers={**admin_header, "If-None-Match": f'"other", W/{etag}'})
            assert listed.status_code == HTTP_304_NOT_MODIFIED

            # Another user sees other unread counts and permissions, so the tag is not shared.
            other_user = client.get(path, headers={**engineer_header, "If-None-Match": etag})
            assert other_user.status_code == HTTP_200_OK

            response = client.post(
                "/comments/", json={"comment": "New comment", "questionId": question["id"]}, headers=engineer_header
            )
            assert response.status_code == HTTP_201_CREATED, response.text

            changed = client.get(path, headers={**admin_header, "If-None-Match": etag})
            assert changed.status_code == HTTP_200_OK
            assert changed.headers["ETag"] != etag
            assert changed.json()[0]["noUnreadComments"] == 1
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)
