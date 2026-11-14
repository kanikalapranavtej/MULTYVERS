def test_category_page_requires_admin(client):
    response = client.get("/admin/categories")
    assert response.status_code in (302, 401)

