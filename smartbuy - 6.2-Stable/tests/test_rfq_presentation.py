from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.main import app


def _login(client):
    response = client.post(
        "/login",
        data={
            "email": "admin@smartbuy.local",
            "password": "SmartBuy@123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_rfq_page_and_actions(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "rfq.db")
    database.init_db()

    with TestClient(app) as client:
        _login(client)
        response = client.get("/purchasing-intelligence/rfq")
        assert response.status_code == 200
        assert "Solicitações de cotação por fornecedor" in response.text
        assert "Enviar pelo WhatsApp" in response.text or "Nenhuma solicitação" in response.text
