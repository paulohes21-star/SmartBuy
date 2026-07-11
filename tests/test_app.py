from fastapi.testclient import TestClient
from app.main import app

def test_login_and_dashboard():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.post(
            "/login",
            data={"email": "admin@smartbuy.local", "password": "SmartBuy@123"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "Bem-vindo" in response.text
        assert client.get("/companies").status_code == 200
