# tests/test_routes.py
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_upload_file():
    response = client.post("/upload/", files={"file": ("test.pdf", b"content")})
    assert response.status_code == 200
    assert response.json() == {"filename": "test.pdf"}
