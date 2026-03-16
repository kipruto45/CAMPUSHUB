"""Regression tests for API docs and schema endpoints."""


def test_root_redirects_to_api_docs(api_client):
    response = api_client.get("/", follow=False)

    assert response.status_code == 302
    assert response["Location"].endswith("/api/docs/")


def test_schema_endpoint_works(api_client):
    response = api_client.get("/api/schema/")

    assert response.status_code == 200
    assert "openapi" in response.data


def test_swagger_endpoint_works(api_client):
    response = api_client.get("/api/docs/")

    assert response.status_code == 200
    assert b"swagger" in response.content.lower()


def test_redoc_endpoint_works(api_client):
    response = api_client.get("/api/redoc/")

    assert response.status_code == 200
    assert b"redoc" in response.content.lower()
