from http import HTTPStatus


def _headers(test_client):
    response = test_client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == HTTPStatus.OK
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_can_broadcast_and_user_can_read(test_client, init_test_database):
    headers = _headers(test_client)
    published = test_client.post(
        "/api/admin/notifications",
        headers=headers,
        json={
            "audience": "active_users",
            "title": "维护通知",
            "body_markdown": "**今晚维护**",
        },
    )
    assert published.status_code == HTTPStatus.CREATED, published.text
    assert published.json()["recipient_count"] == 1
    notification_id = published.json()["id"]
    updated = test_client.patch(
        f"/api/admin/notifications/{notification_id}",
        headers=headers,
        json={"title": "维护更新", "body_markdown": "**已更新**"},
    )
    assert updated.status_code == HTTPStatus.OK, updated.text
    assert updated.json()["recipient_count"] == 1
    assert updated.json()["title"] == "维护更新"

    summary = test_client.get("/api/notifications/summary", headers=headers)
    assert summary.status_code == HTTPStatus.OK
    assert summary.json()["unread_count"] == 1
    notification_id = summary.json()["items"][0]["id"]
    assert (
        test_client.post(
            f"/api/notifications/{notification_id}/read", headers=headers
        ).status_code
        == HTTPStatus.NO_CONTENT
    )
    assert (
        test_client.get("/api/notifications/summary", headers=headers).json()[
            "unread_count"
        ]
        == 0
    )


def test_specified_recipients_must_be_active(test_client, init_test_database):
    headers = _headers(test_client)
    response = test_client.post(
        "/api/admin/notifications",
        headers=headers,
        json={
            "audience": "users",
            "recipient_user_ids": [999999],
            "title": "x",
            "body_markdown": "x",
        },
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
