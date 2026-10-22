from httpx import Headers
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK, HTTP_201_CREATED, HTTP_204_NO_CONTENT
from litestar.testing import TestClient

from ._fixtures import (
    ADMIN_EMAIL,
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


def _last_comment_author_email(client: TestClient[Litestar], headers: Headers, path: str) -> str | None:
    response = client.get(path, headers=headers)
    assert response.status_code == HTTP_200_OK, response.text
    author = response.json()[0]["lastCommentAuthor"]
    return author["email"] if author else None


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
            assert _last_comment_author_email(client, admin_header, paths[0]) is None

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

                # The last commenter is reported regardless of read state.
                assert _last_comment_author_email(client, admin_header, path) == ENGINEER_EMAIL, path
                assert _last_comment_author_email(client, engineer_header, path) == ENGINEER_EMAIL, path

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
            assert _last_comment_author_email(client, engineer_header, paths[0]) == ADMIN_EMAIL
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_mark_comments_read_unknown_question(test_client: TestClient[Litestar], admin_header: Headers) -> None:
    with test_client as client:
        admin_header = login(client)
        response = client.post("/comments/00000000-0000-0000-0000-000000000000/read", headers=admin_header)
        assert response.status_code == 404, response.text


def test_question_detail_identifies_each_comment_and_its_author(
    test_client: TestClient[Litestar],
    admin_header: Headers,
) -> None:
    with test_client as client:
        admin_header = login(client)
        engineer_header = login(client, ENGINEER_EMAIL)
        project = create_project(client, admin_header, engineers=[ENGINEER_EMAIL])
        group = create_group(client, admin_header, project["id"])
        question = create_question(client, admin_header, group["id"])

        try:
            _comment(client, engineer_header, question["id"], "Engineer comment")
            _comment(client, admin_header, question["id"], "Admin comment")

            response = client.get(f"/questions/{question['id']}", headers=admin_header)
            assert response.status_code == HTTP_200_OK, response.text
            comments = response.json()["comments"]
            # The frontend keys comments by id; without it a new comment reuses another comment's avatar.
            assert len({comment["id"] for comment in comments}) == 2
            assert {comment["comment"]: comment["author"]["email"] for comment in comments} == {
                "Engineer comment": ENGINEER_EMAIL,
                "Admin comment": ADMIN_EMAIL,
            }
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_mark_last_comment_unread(test_client: TestClient[Litestar], admin_header: Headers) -> None:
    with test_client as client:
        admin_header = login(client)
        engineer_header = login(client, ENGINEER_EMAIL)
        project = create_project(client, admin_header, engineers=[ENGINEER_EMAIL])
        group = create_group(client, admin_header, project["id"])
        question = create_question(client, admin_header, group["id"])
        path = f"/questions/by_project/{project['id']}"
        unread_path = f"/comments/{question['id']}/unread"

        try:
            # Nothing written by others: there is nothing to mark.
            _comment(client, admin_header, question["id"], "Own comment")
            assert client.post(unread_path, headers=admin_header).status_code == HTTP_204_NO_CONTENT
            assert _comment_state(client, admin_header, path)[:2] == (1, 0)

            # Without a previous read marker only the latest comment of others becomes unread.
            _comment(client, engineer_header, question["id"], "Single engineer comment")
            client.post(f"/comments/{question['id']}/read", headers=admin_header)
            assert client.post(unread_path, headers=admin_header).status_code == HTTP_204_NO_CONTENT
            total, unread, last_comment = _comment_state(client, admin_header, path)
            assert (total, unread, last_comment["comment"]) == (2, 1, "Single engineer comment")

            # Earlier comments stay read; own comments after the latest foreign one stay read too.
            _comment(client, engineer_header, question["id"], "Latest engineer comment")
            _comment(client, admin_header, question["id"], "Own reply")
            assert client.post(unread_path, headers=admin_header).status_code == HTTP_204_NO_CONTENT
            total, unread, last_comment = _comment_state(client, admin_header, path)
            assert (total, unread, last_comment) == (4, 1, None)

            # Opening the question marks everything read again.
            client.post(f"/comments/{question['id']}/read", headers=admin_header)
            assert _comment_state(client, admin_header, path)[:2] == (4, 0)
        finally:
            client.delete(f"/projects/{project['id']}", headers=admin_header)


def test_mark_last_comment_unread_unknown_question(test_client: TestClient[Litestar], admin_header: Headers) -> None:
    with test_client as client:
        admin_header = login(client)
        response = client.post("/comments/00000000-0000-0000-0000-000000000000/unread", headers=admin_header)
        assert response.status_code == 404, response.text
