from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path


PATCH_DIR = Path(__file__).resolve().parent

if (PATCH_DIR / "app" / "main.py").exists():
    PROJECT_DIR = PATCH_DIR
elif (PATCH_DIR.parent / "app" / "main.py").exists():
    PROJECT_DIR = PATCH_DIR.parent
else:
    print("ERRO: nao encontrei a raiz do SmartBuy.")
    print("Coloque a pasta smartbuy-sprint-5-patch dentro da pasta SmartBuy.")
    sys.exit(1)

APP_DIR = PROJECT_DIR / "app"
required = [
    PROJECT_DIR / "INICIAR_SMARTBUY.bat",
    APP_DIR / "main.py",
    APP_DIR / "database.py",
    APP_DIR / "templates" / "base.html",
]

for path in required:
    if not path.exists():
        print(f"ERRO: arquivo obrigatorio nao encontrado: {path}")
        sys.exit(1)

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = PROJECT_DIR / f"backup_antes_sprint5_{stamp}"

for relative in [
    Path("app/main.py"),
    Path("app/database.py"),
    Path("app/templates/base.html"),
    Path(".gitignore"),
]:
    source = PROJECT_DIR / relative
    if source.exists():
        destination = backup / relative
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
database_text = database_path.read_text(encoding="utf-8")
database_marker = "# SMARTBUY_SPRINT_5_PURCHASING_ENGINE"
if database_marker not in database_text:
    patch = (PATCH_DIR / "patches" / "database_append.py").read_text(
        encoding="utf-8"
    )
    database_path.write_text(
        database_text.rstrip() + "\n\n" + patch.rstrip() + "\n",
        encoding="utf-8",
    )

main_path = APP_DIR / "main.py"
main_text = main_path.read_text(encoding="utf-8")
main_marker = "# SMARTBUY_SPRINT_5_ROUTER"
if main_marker not in main_text:
    patch = (PATCH_DIR / "patches" / "main_append.py").read_text(
        encoding="utf-8"
    )
    main_path.write_text(
        main_text.rstrip() + "\n\n" + patch.rstrip() + "\n",
        encoding="utf-8",
    )

base_path = APP_DIR / "templates" / "base.html"
base_text = base_path.read_text(encoding="utf-8")
menu_marker = "<!-- SMARTBUY_SPRINT_5_MENU -->"
if menu_marker not in base_text:
    menu = (PATCH_DIR / "patches" / "menu.html").read_text(
        encoding="utf-8"
    ).strip()
    if "</nav>" not in base_text:
        print("ERRO: nao encontrei </nav> no template base.")
        print(f"Backup criado em: {backup}")
        sys.exit(1)
    base_text = base_text.replace("</nav>", menu + "\n</nav>", 1)

css_marker = "/static/sprint5.css"
if css_marker not in base_text:
    base_text = base_text.replace(
        "</head>",
        '  <link rel="stylesheet" href="/static/sprint5.css">\n</head>',
        1,
    )
base_path.write_text(base_text, encoding="utf-8")

gitignore_path = PROJECT_DIR / ".gitignore"
gitignore = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
for rule in [
    "backup_antes_sprint*/",
    "smartbuy-sprint-*-patch/",
]:
    if rule not in gitignore:
        gitignore += ("\n" if gitignore and not gitignore.endswith("\n") else "") + rule + "\n"
gitignore_path.write_text(gitignore, encoding="utf-8")

print("Sprint 5 aplicada.")
print(f"Backup criado em: {backup}")
print("O banco sera migrado automaticamente ao iniciar o SmartBuy.")
