from __future__ import annotations

from datetime import datetime
from pathlib import Path
import py_compile
import shutil
import sys
import traceback

PATCH_NAME = "SmartBuy Transfer Intelligence 6.6.0"
ROOT = Path.cwd()
PAYLOAD = Path(__file__).resolve().parent / "module"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / "backups" / f"before_transfer_intelligence_{STAMP}"

FILES = {
    PAYLOAD / "transfer_intelligence.py": ROOT / "app" / "transfer_intelligence.py",
    PAYLOAD / "transfer_intelligence.html": ROOT / "app" / "templates" / "transfer_intelligence.html",
    PAYLOAD / "transfer_intelligence.css": ROOT / "app" / "static" / "transfer_intelligence.css",
}


def require_project() -> None:
    required = [
        ROOT / "app" / "main.py",
        ROOT / "app" / "templates" / "base.html",
        ROOT / "app" / "static",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(
            "Execute este instalador na pasta raiz do SmartBuy. "
            "Arquivos não encontrados: " + ", ".join(missing)
        )


def backup_file(path: Path) -> None:
    if not path.exists():
        return
    destination = BACKUP / path.relative_to(ROOT)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)


def insert_once(text: str, marker: str, addition: str, anchor: str, before: bool = False) -> str:
    if marker in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"Ponto de integração não encontrado: {anchor}")
    return text.replace(anchor, addition + anchor if before else anchor + addition, 1)


def patch_main() -> None:
    path = ROOT / "app" / "main.py"
    backup_file(path)
    text = path.read_text(encoding="utf-8")
    marker = "# SMARTBUY_TRANSFER_INTELLIGENCE_ROUTER"
    addition = """

# SMARTBUY_TRANSFER_INTELLIGENCE_ROUTER
from app.transfer_intelligence import router as transfer_intelligence_router
app.include_router(transfer_intelligence_router)
"""
    anchor = "app.include_router(purchasing_intelligence_router)"
    text = insert_once(text, marker, addition, anchor)
    path.write_text(text, encoding="utf-8")


def patch_base() -> None:
    path = ROOT / "app" / "templates" / "base.html"
    backup_file(path)
    text = path.read_text(encoding="utf-8")

    css_marker = "transfer_intelligence.css"
    if css_marker not in text:
        head = "</head>"
        if head not in text:
            raise RuntimeError("Tag </head> não encontrada em app/templates/base.html")
        text = text.replace(
            head,
            '<link rel="stylesheet" href="/static/transfer_intelligence.css">\n</head>',
            1,
        )

    menu_marker = "SMARTBUY_TRANSFER_INTELLIGENCE_MENU"
    if menu_marker not in text:
        preferred_anchor = '<a href="/purchasing-intelligence">Inteligência de compras</a>'
        menu = """
<!-- SMARTBUY_TRANSFER_INTELLIGENCE_MENU -->
<a href="/transfer-intelligence">Transferências inteligentes</a>
"""
        if preferred_anchor in text:
            text = text.replace(preferred_anchor, preferred_anchor + menu, 1)
        elif "</nav>" in text:
            text = text.replace("</nav>", menu + "</nav>", 1)
        else:
            raise RuntimeError("Menu lateral não encontrado em app/templates/base.html")

    path.write_text(text, encoding="utf-8")


def copy_payload() -> None:
    for source, destination in FILES.items():
        if not source.exists():
            raise RuntimeError(f"Payload ausente: {source.name}")
        backup_file(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def validate() -> None:
    py_compile.compile(str(ROOT / "app" / "transfer_intelligence.py"), doraise=True)
    py_compile.compile(str(ROOT / "app" / "main.py"), doraise=True)

    main_text = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    base_text = (ROOT / "app" / "templates" / "base.html").read_text(encoding="utf-8")
    checks = {
        "router incluído": "transfer_intelligence_router" in main_text,
        "menu incluído": "/transfer-intelligence" in base_text,
        "CSS incluído": "transfer_intelligence.css" in base_text,
        "template copiado": (ROOT / "app" / "templates" / "transfer_intelligence.html").exists(),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise RuntimeError("Validação falhou: " + ", ".join(failed))


def rollback() -> None:
    if not BACKUP.exists():
        return
    for source in sorted(BACKUP.rglob("*")):
        if source.is_file():
            destination = ROOT / source.relative_to(BACKUP)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    # Arquivos novos sem versão anterior.
    for destination in FILES.values():
        original = BACKUP / destination.relative_to(ROOT)
        if not original.exists() and destination.exists():
            destination.unlink()


def main() -> int:
    print("=" * 66)
    print(PATCH_NAME)
    print("=" * 66)
    try:
        require_project()
        BACKUP.mkdir(parents=True, exist_ok=True)
        copy_payload()
        patch_main()
        patch_base()
        validate()
        print("\nPATCH APLICADO COM SUCESSO.")
        print(f"Backup: {BACKUP}")
        print("Abra: http://127.0.0.1:8000/transfer-intelligence")
        return 0
    except Exception as exc:
        print("\nERRO:", exc)
        traceback.print_exc()
        print("\nRestaurando backup...")
        rollback()
        print("Rollback concluído.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
