from __future__ import annotations

import py_compile
import shutil
import sys
from datetime import datetime
from pathlib import Path


PATCH_DIR = Path(__file__).resolve().parent

if (PATCH_DIR.parent / "app" / "integration_core.py").exists():
    PROJECT_DIR = PATCH_DIR.parent
elif (PATCH_DIR / "app" / "integration_core.py").exists():
    PROJECT_DIR = PATCH_DIR
else:
    print("ERRO: coloque esta pasta dentro da raiz do projeto SmartBuy.")
    sys.exit(1)

required = [
    PROJECT_DIR / "INICIAR_SMARTBUY.bat",
    PROJECT_DIR / "app" / "main.py",
    PROJECT_DIR / "app" / "integration_core.py",
    PROJECT_DIR / "app" / "templates" / "integration_core.html",
    PROJECT_DIR / "app" / "static" / "sprint6.css",
    PROJECT_DIR / "app" / "purchasing_intelligence.py",
]

for path in required:
    if not path.exists():
        print(f"ERRO: arquivo obrigatório não encontrado: {path}")
        print("Confirme que a Sprint 6 funcional foi aplicada antes da Sprint 6.2.")
        sys.exit(1)

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = PROJECT_DIR / f"backup_antes_sprint6_2_{stamp}"
targets = [
    Path("app/integration_core.py"),
    Path("app/templates/integration_core.html"),
    Path("app/static/sprint6.css"),
    Path("app/static/sprint6_enterprise.js"),
    Path("tests/test_sprint6_2_enterprise.py"),
    Path("docs/SPRINT_6_2_ENTERPRISE_FASE_A.md"),
    Path("CHANGELOG_SPRINT_6_2.md"),
]

for relative in targets:
    current = PROJECT_DIR / relative
    if current.exists():
        destination = backup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(current, destination)

files_dir = PATCH_DIR / "files"
for source in files_dir.rglob("*"):
    if source.is_file():
        relative = source.relative_to(files_dir)
        destination = PROJECT_DIR / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

for relative in (
    Path("app/integration_core.py"),
    Path("tests/test_sprint6_2_enterprise.py"),
):
    py_compile.compile(str(PROJECT_DIR / relative), doraise=True)

print("Sprint 6.2 Enterprise — Fase A aplicada.")
print(f"Backup criado em: {backup}")
print("Nenhuma migração de banco foi necessária.")
print("Execute INICIAR_SMARTBUY.bat e valide /integration-core.")
