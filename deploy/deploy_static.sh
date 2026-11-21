#!/usr/bin/env bash
# #89/#927: despliegue VERSIONADO de estaticos web/ -> raiz servida por Caddy (/srv/x402/unsweep).
# Sustituye la copia manual. Nunca toca secretos.
# Uso:
#   deploy/deploy_static.sh --dry-run        # muestra cambios, no escribe
#   deploy/deploy_static.sh                  # backup + rsync + verificacion de hashes
#   deploy/deploy_static.sh --rollback DIR   # restaura un backup previo
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${UNSWEEP_STATIC_DEST:-/opt/aire/workspace/projects/x402-discovery/static/unsweep}"
BACKUP_ROOT="${UNSWEEP_STATIC_BACKUP:-/opt/aire/backups/unsweep-static}"
MODE="${1:-deploy}"

log(){ echo "[deploy_static] $*"; }
die(){ echo "[deploy_static] ERROR: $*" >&2; exit 1; }

command -v rsync >/dev/null || die "rsync no instalado"
[ -d "$DEST" ] || die "destino inexistente: $DEST"

if [ "$MODE" = "--rollback" ]; then
  SRC="${2:-}"; [ -n "$SRC" ] && [ -d "$SRC" ] || die "--rollback requiere un directorio de backup existente"
  rsync -a --delete "$SRC"/ "$DEST"/
  log "rollback aplicado desde $SRC"
  exit 0
fi

cd "$REPO"
# Guardas: arbol limpio en web/ y HEAD publicado en el remoto (lo desplegado == lo versionado)
[ -z "$(git status --porcelain -- web/)" ] || die "web/ tiene cambios sin commit"
HEAD_SHA="$(git rev-parse HEAD)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "${ALLOW_UNPUSHED:-0}" != "1" ]; then
  REMOTE_SHA="$(git ls-remote origin "refs/heads/$BRANCH" 2>/dev/null | cut -f1)"
  [ "$REMOTE_SHA" = "$HEAD_SHA" ] || die "HEAD $HEAD_SHA no coincide con origin/$BRANCH (${REMOTE_SHA:-ausente})"
fi

RSYNC_OPTS=(-a --delete --checksum --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r --exclude='.git*')

if [ "$MODE" = "--dry-run" ]; then
  rsync "${RSYNC_OPTS[@]}" --dry-run --itemize-changes web/ "$DEST"/
  log "dry-run OK (commit $HEAD_SHA)"
  exit 0
fi
[ "$MODE" = "deploy" ] || die "modo desconocido: $MODE"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$BACKUP_ROOT/$TS"
mkdir -p "$BK"
rsync -a "$DEST"/ "$BK"/
log "backup previo: $BK"

rsync "${RSYNC_OPTS[@]}" web/ "$DEST"/

# Verificacion: hash de cada archivo clave desplegado == blob del commit
fail=0
for f in index.html assets/app.js; do
  want="$(git show "HEAD:web/$f" | sha256sum | cut -d' ' -f1)"
  got="$(sha256sum "$DEST/$f" | cut -d' ' -f1)"
  if [ "$want" = "$got" ]; then log "OK $f $got"; else log "MISMATCH $f want=$want got=$got"; fail=1; fi
done
if [ "$fail" != 0 ]; then
  rsync -a --delete "$BK"/ "$DEST"/
  die "hash distinto; rollback automatico desde $BK"
fi
echo "$HEAD_SHA" > "$BK.deployed_over"
log "desplegado commit $HEAD_SHA en $DEST (rollback: $0 --rollback $BK)"
