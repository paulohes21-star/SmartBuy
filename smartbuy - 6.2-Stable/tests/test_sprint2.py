from fastapi.testclient import TestClient
from app.main import app

def login(client):
    return client.post('/login',data={'email':'admin@smartbuy.local','password':'SmartBuy@123'},follow_redirects=True)

def test_product_pages_and_creation():
    with TestClient(app) as client:
        assert login(client).status_code==200
        assert client.get('/products').status_code==200
        # Unique values avoid conflict with persistent local test DB.
        response=client.post('/products/new',data={'internal_code':'TEST-SPRINT2','description':'Produto Teste Sprint 2','unit_id':'1','ipi_rate':'0','icms_rate':'0','active':'1','minimum_stock':'0','maximum_stock':'0','lead_time_days':'0','average_cost':'0','last_cost':'0','current_stock':'0'},follow_redirects=True)
        assert response.status_code in (200,409)

def test_excel_template():
    with TestClient(app) as client:
        login(client)
        response=client.get('/products/template.xlsx')
        assert response.status_code==200
        assert response.headers['content-type'].startswith('application/vnd.openxmlformats')
