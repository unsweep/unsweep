#!/usr/bin/env bash
# #928/#100-A: despliegue VERSIONADO del relayer unsweep-relayer. Solo imprime NOMBRES de variables.
# Uso: deploy/deploy_relayer.sh --commit <SHA40> [--dry-run]
# Exit: 0 OK | 1 precheck fallido sin cambios | 2 fallo + ROLLBACK OK | 3 fallo + ROLLBACK FALLIDO
set -euo pipefail
if [ -z "${_DR_COPY:-}" ]; then
  _t="$(mktemp /tmp/deploy_relayer.XXXXXX)"; cp "$0" "$_t"; export _DR_COPY="$_t"; exec bash "$_t" "$@"
fi
trap 'rm -f "$_DR_COPY"' EXIT
REPO="${UNSWEEP_REPO:-/opt/aire/workspace/projects/unsweep}"
ENV_FILE="${UNSWEEP_ENV_FILE:-/opt/aire/unsweep-relayer.env}"
HEALTH_URL="${UNSWEEP_HEALTH_URL:-https://unsweep.com/api/health}"
HEALTH_MAX="${HEALTH_MAX:-20}"; HEALTH_SLEEP="${HEALTH_SLEEP:-3}"; HEALTH_NEED=3
DOCKER="${DOCKER:-docker}"; CURL="${CURL:-curl}"
CONTAINER=unsweep-relayer; IMAGE=unsweep-relayer:latest
ALLOWED="TURNSTILE_SECRET TURNSTILE_SITEKEY OPS_PK BASE_RPC_URL ETH_RPC_URL OP_RPC_URL"
FORBIDDEN="PAYER_PK GITHUB_TOKEN ETHERSCAN_API_KEY"
log(){ echo "[deploy_relayer] $*"; }
die(){ echo "[deploy_relayer] PRECHECK FALLIDO: $*" >&2; exit 1; }
SHA=""; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) SHA="${2:-}"; shift; [ $# -gt 0 ] && shift ;;
    --dry-run) DRY=1; shift ;;
    *) die "argumento desconocido: $1" ;;
  esac
done
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || die "--commit requiere SHA completo de 40 hex"
compose(){ "$DOCKER" compose -p unsweep -f "$REPO/deploy/docker-compose.yml" "$@"; }
env_file_names(){ sed -e 's/^[[:space:]]*//' -e '/^#/d' -e '/^$/d' "$ENV_FILE" | cut -d= -f1; }
container_env_names(){ "$DOCKER" inspect "$CONTAINER" --format '{{range .Config.Env}}{{println .}}{{end}}' | cut -d= -f1 | sed '/^$/d'; }
check_container_env(){
  local names f bad=0
  names="$(container_env_names)" || { log "no se pudo inspeccionar $CONTAINER"; return 1; }
  log "env del contenedor (solo nombres): $(echo "$names" | sort | tr '\n' ' ')"
  for f in $FORBIDDEN; do echo "$names" | grep -qx "$f" && { log "PROHIBIDA en el contenedor: $f"; bad=1; }; done
  [ "$bad" = 0 ] && log "secretos prohibidos en el contenedor: ninguno"
  return "$bad"
}
health_once(){
  local hf code r
  hf="$(mktemp)"
  code="$("$CURL" -sS -m 10 -o "$hf" -w '%{http_code}' "$HEALTH_URL" 2>/dev/null)" || code=000
  r="$(python3 -c 'import json,sys
try:
    d=json.load(open(sys.argv[1])); print(d.get("ok"),d.get("chainId"),d.get("mainnet"))
except Exception:
    print("json_invalido")' "$hf")"
  rm -f "$hf"; log "health http=$code ok,chainId,mainnet=$r"
  [ "$code" = 200 ] && [ "$r" = "True 8453 True" ]
}
wait_health(){
  local i consec=0
  for i in $(seq 1 "$HEALTH_MAX"); do
    if health_once; then consec=$((consec+1)); else consec=0; fi
    [ "$consec" -ge "$HEALTH_NEED" ] && { log "health OK $consec/$HEALTH_NEED consecutivos"; return 0; }
    sleep "$HEALTH_SLEEP"
  done
  log "health FALLIDO tras $HEALTH_MAX intentos"; return 1
}
# ---------- PRECHECKS (sin efectos) ----------
cd "$REPO"
[ -z "$(git status --porcelain --untracked-files=no)" ] || die "arbol de $REPO con cambios sin commit"
git fetch -q origin || die "git fetch origin fallo"
git cat-file -e "$SHA^{commit}" 2>/dev/null || die "commit $SHA no existe tras fetch"
git ls-remote origin | cut -f1 | grep -qx "$SHA" || die "$SHA no es punta de ninguna rama de origin (no publicado)"
[ -f "$ENV_FILE" ] || die "env_file inexistente: $ENV_FILE"
[ "$(stat -c %a "$ENV_FILE")" = 600 ] || die "env_file debe tener permisos 600"
for n in $(env_file_names); do
  case " $ALLOWED " in *" $n "*) ;; *) die "env_file contiene nombre no permitido: $n" ;; esac
done
log "env_file minimo OK (solo nombres): $(env_file_names | tr '\n' ' ')"
PREV_SHA="$(git rev-parse HEAD)"
PREV_REF="$(git symbolic-ref -q --short HEAD || echo "$PREV_SHA")"
PREV_IMG="$("$DOCKER" inspect "$CONTAINER" --format '{{.Image}}' 2>/dev/null || true)"
[ -n "$PREV_IMG" ] || die "no hay contenedor $CONTAINER en ejecucion para rollback"
RB_TAG="unsweep-relayer:rollback-${PREV_SHA:0:8}"
log "plan: $PREV_REF ($PREV_SHA) -> $SHA; imagen previa ${PREV_IMG:0:19} -> $RB_TAG"
if [ "$DRY" = 1 ]; then log "DRY-RUN OK: prechecks superados, sin cambios"; exit 0; fi

# ---------- ROLLBACK ----------
rollback(){
  log "ROLLBACK -> $PREV_REF ($PREV_SHA), imagen $RB_TAG"
  git checkout -f -q "$PREV_REF" &&
  "$DOCKER" tag "$RB_TAG" "$IMAGE" &&
  compose up -d --no-build --force-recreate relayer &&
  wait_health && check_container_env
}
fail(){
  log "FALLO: $1"
  if rollback; then log "ROLLBACK OK"; exit 2; fi
  log "ROLLBACK FALLIDO: intervencion necesaria"; exit 3
}

# ---------- DESPLIEGUE ----------
"$DOCKER" tag "$PREV_IMG" "$RB_TAG" || die "no se pudo etiquetar la imagen previa"
log "imagen previa etiquetada como $RB_TAG"
git checkout -q --detach "$SHA" || fail "checkout $SHA"
compose up -d --build --force-recreate relayer || fail "compose up --build"
wait_health || fail "health"
check_container_env || fail "entorno del contenedor con secretos prohibidos"
log "DESPLIEGUE OK: $SHA (rollback disponible: $RB_TAG)"
exit 0
