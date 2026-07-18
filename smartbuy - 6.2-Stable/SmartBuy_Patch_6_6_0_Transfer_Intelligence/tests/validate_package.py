from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parents[1]
py_compile.compile(str(ROOT / "module" / "transfer_intelligence.py"), doraise=True)
py_compile.compile(str(ROOT / "install_patch.py"), doraise=True)
assert "transfer-intelligence" in (ROOT / "module" / "transfer_intelligence.html").read_text(encoding="utf-8")
assert ".ti-page" in (ROOT / "module" / "transfer_intelligence.css").read_text(encoding="utf-8")
print("Pacote validado com sucesso.")
