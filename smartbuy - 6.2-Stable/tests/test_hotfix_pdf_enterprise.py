from pathlib import Path

from fastapi.testclient import TestClient

from app import database
from app.main import app


def _login(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={
            "email": "admin@smartbuy.local",
            "password": "SmartBuy@123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_pdf_button_uses_dedicated_route():
    template = Path(
        "app/templates/quotation_requests.html"
    ).read_text(encoding="utf-8")

    assert "/purchasing-intelligence/rfq/pdf/" in template
    assert "printRfq(" not in template
    assert 'target="_blank"' in template


def test_pdf_unknown_request_returns_404(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "pdf-404.db")
    database.init_db()

    with TestClient(app) as client:
        _login(client)
        response = client.get(
            "/purchasing-intelligence/rfq/pdf/SC-INEXISTENTE"
            "?analysis_months=3"
        )
        assert response.status_code == 404
