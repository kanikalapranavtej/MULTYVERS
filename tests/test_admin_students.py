def test_student_management_requires_admin(client):
    response = client.get("/admin/students")
    assert response.status_code == 302


def test_admin_can_view_student_directory(client):
    client.post("/auth/login", data={"email": "admin@test.com", "password": "password123"})
    response = client.get("/admin/students")
    assert response.status_code == 200
    assert b"Student management" in response.data
    assert b"student@test.com" in response.data


def test_student_cannot_view_student_directory(client):
    client.post("/auth/login", data={"email": "student@test.com", "password": "password123"})
    assert client.get("/admin/students").status_code == 403


def test_admin_can_deactivate_and_reactivate_student(client, app):
    client.post("/auth/login", data={"email": "admin@test.com", "password": "password123"})
    response = client.post("/admin/students", data={"student_id": 2, "action": "deactivate"}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        from app.database import get_db
        assert get_db().execute("SELECT is_active FROM users WHERE user_id=2").fetchone()["is_active"] == 0
    client.post("/admin/students", data={"student_id": 2, "action": "reactivate"})
    with app.app_context():
        from app.database import get_db
        assert get_db().execute("SELECT is_active FROM users WHERE user_id=2").fetchone()["is_active"] == 1
