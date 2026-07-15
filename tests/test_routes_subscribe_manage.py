import sqlite3


def test_subscribe_page_renders_without_npl(client, ready_db):
    r = client.get("/subscribe")
    assert r.status_code == 200
    assert "Meddela mig när det finns igen" in r.get_data(as_text=True)


def test_subscribe_page_renders_with_resolved_medicine(client, ready_db):
    con = sqlite3.connect(ready_db)
    con.execute("INSERT INTO medications (npl_pack_id, name) VALUES ('11111111111111', 'Testpillret 10 mg')")
    con.commit()
    con.close()

    r = client.get("/subscribe?npl=11111111111111")
    assert r.status_code == 200
    assert "Testpillret 10 mg" in r.get_data(as_text=True)


def test_manage_page_renders_subscriptions(client, ready_db):
    con = sqlite3.connect(ready_db)
    con.execute("INSERT INTO subscribers (id, email) VALUES (1, 'anna@example.se')")
    con.execute("INSERT INTO medications (npl_pack_id, name) VALUES ('22222222222222', 'Testpillret 20 mg')")
    con.execute(
        "INSERT INTO subscriptions (subscriber_id, npl_pack_id, expires_at, active) "
        "VALUES (1, '22222222222222', '2026-12-31 00:00:00', 1)"
    )
    con.execute(
        "INSERT INTO tokens (token, type, subscriber_id, expires_at) "
        "VALUES ('mgmt-token-1', 'manage', 1, '2099-01-01 00:00:00')"
    )
    con.commit()
    con.close()

    r = client.get("/manage/mgmt-token-1")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "anna@example.se" in body
    assert "Testpillret 20 mg" in body
    assert "Löper ut 2026-12-31" in body


def test_manage_page_invalid_token_renders_message_page(client, ready_db):
    r = client.get("/manage/does-not-exist")
    assert r.status_code == 404
    assert "hittades inte" in r.get_data(as_text=True)
