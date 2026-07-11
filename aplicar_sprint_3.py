from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path


PATCH_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PATCH_DIR.parent
APP_DIR = PROJECT_DIR / "app"

REQUIRED = [
    PROJECT_DIR / "INICIAR_SMARTBUY.bat",
    APP_DIR / "main.py",
    APP_DIR / "database.py",
    APP_DIR / "templates" / "base.html",
]

for required in REQUIRED:
    if not required.exists():
        print(f"ERRO: arquivo obrigatório não encontrado: {required}")
        print("Coloque a pasta smartbuy-sprint-3-patch dentro da raiz do projeto SmartBuy.")
        sys.exit(1)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = PROJECT_DIR / f"backup_antes_sprint3_{timestamp}"
backup_dir.mkdir(parents=True, exist_ok=True)

for relative in [
    Path("app/main.py"),
    Path("app/database.py"),
    Path("app/templates/base.html"),
]:
    source = PROJECT_DIR / relative
    destination = backup_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)

files_dir = PATCH_DIR / "files"
for source in files_dir.rglob("*"):
    if source.is_file():
        relative = source.relative_to(files_dir)
        destination = PROJECT_DIR / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

database_path = APP_DIR / "database.py"
database_content = database_path.read_text(encoding="utf-8")
database_marker = "# SMARTBUY_SPRINT_3_MASTER_DATA"

if database_marker not in database_content:
    database_patch = (PATCH_DIR / "patches" / "database_append.py").read_text(encoding="utf-8")
    database_path.write_text(
        database_content.rstrip() + "\n\n" + database_patch.rstrip() + "\n",
        encoding="utf-8",
    )

main_path = APP_DIR / "main.py"
main_content = main_path.read_text(encoding="utf-8")
main_marker = "# SMARTBUY_SPRINT_3_ROUTER"

if main_marker not in main_content:
    main_patch = (PATCH_DIR / "patches" / "main_append.py").read_text(encoding="utf-8")
    main_path.write_text(
        main_content.rstrip() + "\n\n" + main_patch.rstrip() + "\n",
        encoding="utf-8",
    )

base_path = APP_DIR / "templates" / "base.html"
base_content = base_path.read_text(encoding="utf-8")
menu_marker = "<!-- SMARTBUY_SPRINT_3_MENU -->"

if menu_marker not in base_content:
    menu_html = (PATCH_DIR / "patches" / "menu.html").read_text(encoding="utf-8").strip()
    if "</nav>" not in base_content:
        print("ERRO: não encontrei </nav> em app/templates/base.html.")
        print(f"Backup criado em: {backup_dir}")
        sys.exit(1)
    base_content = base_content.replace("</nav>", menu_html + "\n</nav>", 1)
    base_path.write_text(base_content, encoding="utf-8")

style_path = APP_DIR / "static" / "style.css"
if not style_path.exists():
    style_path = APP_DIR / "static" / "styles.css"

style_marker = "/* SMARTBUY_SPRINT_3_STYLES */"
if style_path.exists():
    style_content = style_path.read_text(encoding="utf-8")
    if style_marker not in style_content:
        sprint_styles = (PATCH_DIR / "patches" / "styles_append.css").read_text(encoding="utf-8")
        style_path.write_text(
            style_content.rstrip() + "\n\n" + sprint_styles.rstrip() + "\n",
            encoding="utf-8",
        )

print("Sprint 3 aplicada.")
print(f"Backup dos arquivos alterados: {backup_dir}")
print("Próximo passo: execute INICIAR_SMARTBUY.bat.")
