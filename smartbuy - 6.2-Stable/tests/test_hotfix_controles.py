from pathlib import Path

def test_recalcular_omite_empresa_vazia():
    template = Path(
        "app/templates/purchasing_intelligence.html"
    ).read_text(encoding="utf-8")
    assert 'id="purchase-recalculate-form"' in template
    assert "submitPurchaseRecalculation(event)" in template
    assert 'company.value.trim() !== ""' in template
    assert '"Recalculando..."' in template

def test_pdf_continua_real_e_estilizado():
    template = Path(
        "app/templates/quotation_requests.html"
    ).read_text(encoding="utf-8")
    css = Path(
        "app/static/hotfix_recalcular_pdf_button.css"
    ).read_text(encoding="utf-8")
    assert "/purchasing-intelligence/rfq/pdf/" in template
    assert 'class="rfq-pdf-button"' in template
    assert "display: inline-flex" in css
