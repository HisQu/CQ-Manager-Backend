from httpx import Headers
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT
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


def _comment(client: TestClient[Litestar], headers: Headers, question_id: str, text: str) -> None:
    response = client.post("/comments/", json={"comment": text, "questionId": question_id}, headers=headers)
    assert response.status_code == HTTP_201_CREATED, response.text


def _list_paths(project_id: str, group_id: str) -> list[str]:
    return [
        f"/questions/by_project/{project_id}",
        f"/questions/by_project/{project_id}/unified",
        f"/questions/by_group/{group_id}",
        f"/questions/by_group/{group_id}/unified",
    ]


def _comment_state(client: TestClient[Litestar], headers: Headers, path: str) -> tuple[int, int, dict | None]:
    response = client.get(path, headers=headers)
    assert response.status_code == HTTP_200_OK, response.text
    question = response.json()[0]
    return question["noComments"], question["noUnreadComments"], question["lastComment"]


def test_question_lists_report_unread_comments_per_user(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        admin_header = login(client)
        engineer_header = login(client, ENGINEER_EMAIL)
        project = create_project(client, admin_header, engineers=[ENGINEER_EMAIL])
        group = create_group(client, admin_header, project["id"])
        question = create_question(client, admin_header, group["id"])
        paths = _list_paths(project["id"], group["id"])

        try:
            assert _comment_state(client, admin_header, paths[0]) == (0, 0, None)

            _comment(client, engineer_header, question["id"], "First comment")
            _comment(client, engineer_header, question["id"], "Latest comment")

            for path in paths:
                total, unread, last_comment = _comment_state(client, admin_header, path)
                assert (total, unread) == (2, 2), path
                assert last_comment["comment"] == "Latest comment", path
                assert last_comment["author"], path
                assert last_comment["createdAt"], path

                # Own comments never count as unread.
                assert _comment_state(client, engineer_header, path) == (2, 0, None), path

            response = client.post(f"/comments/{question['id']}/read", headers=admin_header)
            assert response.status_code == HTTP_204_NO_CONTENT, response.text
            for path in paths:
                assert _comment_state(client, admin_header, path) == (2, 0, None), path

            # Answering marks the thread as read for the author and is unread for everybody else.
            _comment(client, admin_header, question["id"], "Answer")
            assert _comment_state(client, admin_header, paths[0]) == (3, 0, None)
            total, unread, last_comment = _comment_state(client, engineer_header, paths[0])
            assert (total, unread) == (3, 1)
            assert last_comment["comment"] == "Answer"
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_mark_comments_read_unknown_question(test_client: TestClient[Litestar], admin_header: Headers) -> None:
    with test_client as client:
        admin_header = login(client)
        response = client.post("/comments/00000000-0000-0000-0000-000000000000/read", headers=admin_header)
        assert response.status_code == 404, response.text
