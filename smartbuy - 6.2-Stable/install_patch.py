from pathlib import Path
from datetime import datetime
import shutil, py_compile, traceback

ROOT = Path.cwd()
PAYLOAD = Path(__file__).resolve().parent / "module"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / "backups" / f"before_executive_cockpit_6_7_0_{STAMP}"

FILES = {
    PAYLOAD/"executive_cockpit.py": ROOT/"app"/"executive_cockpit.py",
    PAYLOAD/"executive_cockpit.html": ROOT/"app"/"templates"/"executive_cockpit.html",
    PAYLOAD/"executive_cockpit.css": ROOT/"app"/"static"/"executive_cockpit.css",
}

def backup(path):
    if not path.exists(): return
    dst = BACKUP / path.relative_to(ROOT)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)

def restore():
    if not BACKUP.exists(): return
    for src in BACKUP.rglob("*"):
        if src.is_file():
            dst = ROOT / src.relative_to(BACKUP)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

def patch_main():
    path = ROOT/"app"/"main.py"
    backup(path)
    text = path.read_text(encoding="utf-8")
    marker = "# SMARTBUY_EXECUTIVE_COCKPIT_ROUTER"
    if marker not in text:
        addition = """

# SMARTBUY_EXECUTIVE_COCKPIT_ROUTER
from app.executive_cockpit import router as executive_cockpit_router
app.include_router(executive_cockpit_router)
"""
        text += addition
        path.write_text(text, encoding="utf-8")

def patch_base():
    path = ROOT/"app"/"templates"/"base.html"
    backup(path)
    text = path.read_text(encoding="utf-8")
    if "executive_cockpit.css" not in text:
        if "</head>" not in text: raise RuntimeError("Tag </head> não encontrada.")
        text = text.replace("</head>", '<link rel="stylesheet" href="/static/executive_cockpit.css">\n</head>', 1)
    if "/executive-cockpit" not in text:
        menu = '\n<!-- SMARTBUY_EXECUTIVE_COCKPIT_MENU -->\n<a href="/executive-cockpit">Cockpit Executivo</a>\n'
        anchor = '<a href="/dashboard">Dashboard</a>'
        if anchor in text:
            text = text.replace(anchor, anchor + menu, 1)
        elif "</nav>" in text:
            text = text.replace("</nav>", menu + "</nav>", 1)
        else:
            raise RuntimeError("Menu lateral não encontrado.")
    path.write_text(text, encoding="utf-8")

def main():
    print("="*68)
    print("SMARTBUY 6.7.0 - EXECUTIVE COCKPIT")
    print("="*68)
    try:
        required = [ROOT/"app"/"main.py", ROOT/"app"/"templates"/"base.html", ROOT/"app"/"transfer_intelligence.py"]
        missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
        if missing: raise RuntimeError("Arquivos ausentes: " + ", ".join(missing))
        for src,dst in FILES.items():
            if not src.exists(): raise RuntimeError("Payload ausente: " + src.name)
            backup(dst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src,dst)
        patch_main()
        patch_base()
        py_compile.compile(str(ROOT/"app"/"executive_cockpit.py"), doraise=True)
        py_compile.compile(str(ROOT/"app"/"main.py"), doraise=True)
        assert "Centro de Oportunidades" in (ROOT/"app"/"templates"/"executive_cockpit.html").read_text(encoding="utf-8")
        print("\nMÓDULO APLICADO COM SUCESSO.")
        print("Backup:", BACKUP)
        print("Abra: http://127.0.0.1:8000/executive-cockpit")
        return 0
    except Exception as exc:
        print("\nERRO:", exc)
        traceback.print_exc()
        restore()
        print("Backup restaurado.")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
