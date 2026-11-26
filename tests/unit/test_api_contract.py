"""Contract checks for the currently implemented HTTP surface."""

from fastapi.testclient import TestClient

from src.api.main import app


def test_openapi_describes_the_implemented_routes() -> None:
    schema = app.openapi()

    assert schema["info"]["title"] == "GroundStack API"
    assert schema["info"]["version"] == "0.1.0"
    assert set(schema["paths"]) == {"/", "/health"}
    assert "200" in schema["paths"]["/health"]["get"]["responses"]


def test_health_endpoint_reports_process_liveness_only() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "message": "Process is responding; dependency readiness is not checked.",
    }


def test_workspace_static_mount_serves_the_existing_page() -> None:
    with TestClient(app) as client:
        response = client.get("/workspace/")

    assert response.status_code == 200
    assert "GroundStack" in response.text
