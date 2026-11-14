def test_student_portal_page_renders_registration_area(client):
    client.post("/auth/login", data={"email": "student@test.com", "password": "password123"})
    response = client.get("/student/portal")
    assert response.status_code == 200
    assert b"My registrations" in response.data
    assert b"Explore events" in response.data


def test_student_portal_rejects_non_student(client):
    client.post("/auth/login", data={"email": "admin@test.com", "password": "password123"})
    assert client.get("/student/portal").status_code == 403
