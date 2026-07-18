from pathlib import Path
import shutil
import sys

root = Path.cwd()
backups = root / "backups"
candidates = sorted(backups.glob("before_transfer_intelligence_*"), reverse=True)
if not candidates:
    print("Nenhum backup do Transfer Intelligence foi encontrado.")
    raise SystemExit(1)

backup = candidates[0]
print("Restaurando:", backup)
for source in backup.rglob("*"):
    if source.is_file():
        destination = root / source.relative_to(backup)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

for relative in [
    Path("app/transfer_intelligence.py"),
    Path("app/templates/transfer_intelligence.html"),
    Path("app/static/transfer_intelligence.css"),
]:
    original = backup / relative
    destination = root / relative
    if not original.exists() and destination.exists():
        destination.unlink()

print("Rollback concluído. Revise app/main.py e base.html caso tenham sido alterados depois do patch.")
