# ./docker/entrypoint.sh

#!/usr/bin/env sh
set -e
export PYTHONPATH=/app
mkdir -p /app/.data /app/reports/outputs

# [CHANGED] Alembic 없으면 자동 create_all로 폴백
if alembic upgrade head; then
  echo "Alembic migrations applied."
else
  echo "No Alembic revisions or upgrade failed — falling back to Base.metadata.create_all"
  python - <<'PY'
from app.db.session import engine
from app.db.models.base import Base
Base.metadata.create_all(bind=engine)
print("create_all done.")
PY
fi

exec "$@"
