from __future__ import annotations
import py_compile, shutil, sys
from datetime import datetime
from pathlib import Path

PATCH_DIR = Path(__file__).resolve().parent
if (PATCH_DIR / 'app' / 'main.py').exists():
    PROJECT_DIR = PATCH_DIR
elif (PATCH_DIR.parent / 'app' / 'main.py').exists():
    PROJECT_DIR = PATCH_DIR.parent
else:
    print('ERRO: coloque esta pasta dentro da raiz do projeto SmartBuy.')
    sys.exit(1)

required = [PROJECT_DIR/'INICIAR_SMARTBUY.bat', PROJECT_DIR/'app/main.py', PROJECT_DIR/'app/database.py', PROJECT_DIR/'app/purchasing_intelligence.py', PROJECT_DIR/'app/purchasing_engine.py', PROJECT_DIR/'app/templates/base.html']
for path in required:
    if not path.exists():
        print(f'ERRO: arquivo base ausente: {path}')
        sys.exit(1)

stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup = PROJECT_DIR / f'backup_antes_sprint6_2_consolidada_{stamp}'
for rel in ['app/main.py','app/database.py','app/templates/base.html','app/integration_core.py','app/templates/integration_core.html','app/static/sprint6.css']:
    src = PROJECT_DIR/rel
    if src.exists():
        dst = backup/rel; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src,dst)

# Restore/copy complete production sources.
for src in (PATCH_DIR/'files').rglob('*'):
    if src.is_file():
        rel = src.relative_to(PATCH_DIR/'files')
        dst = PROJECT_DIR/rel; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src,dst)

# Idempotent schema.
db = PROJECT_DIR/'app/database.py'; text = db.read_text(encoding='utf-8')
if '# SMARTBUY_SPRINT_6_INTEGRATION_CORE' not in text:
    text = text.rstrip()+'\n\n'+(PATCH_DIR/'patches/database_append.py').read_text(encoding='utf-8').rstrip()+'\n'
    db.write_text(text,encoding='utf-8')
    print('Migração idempotente da integração registrada.')
else: print('Migração da integração já registrada.')

# Idempotent router.
main = PROJECT_DIR/'app/main.py'; text = main.read_text(encoding='utf-8')
if '# SMARTBUY_SPRINT_6_ROUTER' not in text:
    text = text.rstrip()+'\n\n'+(PATCH_DIR/'patches/main_append.py').read_text(encoding='utf-8').rstrip()+'\n'
    main.write_text(text,encoding='utf-8')
    print('Router /integration-core registrado.')
else: print('Router /integration-core já registrado.')

# Idempotent CSS and menu.
base = PROJECT_DIR/'app/templates/base.html'; text = base.read_text(encoding='utf-8')
if '/static/sprint6.css' not in text:
    text = text.replace('</head>', '  <link rel="stylesheet" href="/static/sprint6.css">\n</head>', 1)
if '<!-- SMARTBUY_SPRINT_6_MENU -->' not in text:
    menu=(PATCH_DIR/'patches/menu.html').read_text(encoding='utf-8').strip()
    text=text.replace('</nav>', menu+'\n</nav>',1)
base.write_text(text,encoding='utf-8')

# Compile all relevant Python files before declaring success.
for rel in ['app/integration_core.py','app/decision_explain.py','app/integration/connectors.py','app/integration/mapper.py','app/integration/models.py','app/integration/quality.py','app/integration/sync_engine.py','tests/test_sprint6_2_enterprise.py']:
    py_compile.compile(str(PROJECT_DIR/rel), doraise=True)

print('')
print('Sprint 6.2 Enterprise Consolidada aplicada com sucesso.')
print(f'Backup criado em: {backup}')
print('Execute INICIAR_SMARTBUY.bat e valide as rotas.')
