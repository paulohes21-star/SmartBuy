from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path


PATCH_DIR = Path(__file__).resolve().parent

# Funciona tanto com a pasta do patch dentro do projeto quanto com os
# arquivos do patch copiados diretamente para a raiz.
if (PATCH_DIR / "app" / "main.py").exists():
    PROJECT_DIR = PATCH_DIR
elif (PATCH_DIR.parent / "app" / "main.py").exists():
    PROJECT_DIR = PATCH_DIR.parent
else:
    print("ERRO: nao encontrei a raiz do SmartBuy.")
    print("Coloque a pasta smartbuy-sprint-4-patch dentro da pasta SmartBuy.")
    sys.exit(1)

APP_DIR = PROJECT_DIR / "app"
required = [
    PROJECT_DIR / "INICIAR_SMARTBUY.bat",
    APP_DIR / "main.py",
    APP_DIR / "database.py",
    APP_DIR / "templates" / "products.html",
]
for path in required:
    if not path.exists():
        print(f"ERRO: arquivo obrigatorio nao encontrado: {path}")
        sys.exit(1)

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = PROJECT_DIR / f"backup_antes_sprint4_{stamp}"

to_backup = [
    Path("app/main.py"),
    Path("app/database.py"),
    Path("app/templates/products.html"),
    Path("app/templates/product_form.html"),
]
for relative in to_backup:
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
database_marker = "# SMARTBUY_SPRINT_4_INTELLIGENT_PRODUCTS"
if database_marker not in database_text:
    append = (PATCH_DIR / "patches" / "database_append.py").read_text(encoding="utf-8")
    database_path.write_text(
        database_text.rstrip() + "\n\n" + append.rstrip() + "\n",
        encoding="utf-8",
    )

main_path = APP_DIR / "main.py"
main_text = main_path.read_text(encoding="utf-8")
main_marker = "# SMARTBUY_SPRINT_4_ROUTER"
if main_marker not in main_text:
    append = (PATCH_DIR / "patches" / "main_append.py").read_text(encoding="utf-8")
    main_path.write_text(
        main_text.rstrip() + "\n\n" + append.rstrip() + "\n",
        encoding="utf-8",
    )


base_path = APP_DIR / "templates" / "base.html"
base_text = base_path.read_text(encoding="utf-8")
css_marker = "/static/sprint4.css"
if css_marker not in base_text:
    base_text = base_text.replace(
        "</head>",
        '  <link rel="stylesheet" href="/static/sprint4.css">\n</head>',
        1,
    )
    base_path.write_text(base_text, encoding="utf-8")

print("Sprint 4 aplicada.")
print(f"Backup criado em: {backup}")
print("O banco sera migrado automaticamente ao iniciar o SmartBuy.")
