from pathlib import Path
from datetime import datetime
import shutil, py_compile, traceback

ROOT = Path.cwd()
PAYLOAD = Path(__file__).resolve().parent / "module"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / "backups" / f"before_transfer_executive_6_6_2_{STAMP}"
TARGETS = {
    PAYLOAD/"transfer_intelligence.py": ROOT/"app"/"transfer_intelligence.py",
    PAYLOAD/"transfer_intelligence.html": ROOT/"app"/"templates"/"transfer_intelligence.html",
    PAYLOAD/"transfer_intelligence.css": ROOT/"app"/"static"/"transfer_intelligence.css",
}

def restore():
    if not BACKUP.exists(): return
    for src in BACKUP.rglob("*"):
        if src.is_file():
            dst = ROOT / src.relative_to(BACKUP)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

def main():
    print("="*70)
    print("SMARTBUY HOTFIX 6.6.2 - TRANSFER INTELLIGENCE EXECUTIVE")
    print("="*70)
    try:
        required=[ROOT/"app"/"main.py",ROOT/"app"/"transfer_intelligence.py",ROOT/"app"/"templates"/"base.html"]
        missing=[str(p.relative_to(ROOT)) for p in required if not p.exists()]
        if missing: raise RuntimeError("Execute na raiz do SmartBuy. Ausentes: "+", ".join(missing))
        for src,dst in TARGETS.items():
            if not src.exists(): raise RuntimeError("Payload ausente: "+src.name)
            if dst.exists():
                backup=BACKUP/dst.relative_to(ROOT)
                backup.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(dst,backup)
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,dst)
        py_compile.compile(str(ROOT/"app"/"transfer_intelligence.py"),doraise=True)
        html=(ROOT/"app"/"templates"/"transfer_intelligence.html").read_text(encoding="utf-8")
        css=(ROOT/"app"/"static"/"transfer_intelligence.css").read_text(encoding="utf-8")
        if "Centro de Oportunidades" not in html or ".tie-page" not in css:
            raise RuntimeError("Validação visual não concluída.")
        print("\nHOTFIX APLICADO COM SUCESSO.")
        print("Backup:", BACKUP)
        print("Reinicie o SmartBuy e pressione CTRL+F5.")
        return 0
    except Exception as exc:
        print("\nERRO:", exc)
        traceback.print_exc()
        restore()
        print("Backup restaurado.")
        return 1

if __name__=="__main__":
    raise SystemExit(main())
