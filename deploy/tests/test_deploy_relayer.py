"""Tests de deploy/deploy_relayer.sh con stubs de docker/curl y un repo git temporal (sin red ni Docker real)."""
import os, stat, subprocess, pathlib, pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "deploy_relayer.sh"
SECRET_VALUE = "VALOR_SECRETO_NO_DEBE_SALIR"

DOCKER_STUB = r'''#!/usr/bin/env bash
echo "$*" >> "$STATE/docker.log"
if [ "$1" = inspect ]; then
  case "$*" in
    *".Image"*) echo sha256:prev000000000000000000 ;;
    *) cat "$STATE/env" ;;
  esac; exit 0
fi
if [ "$1" = compose ]; then
  case "$*" in
    *--no-build*) echo ok > "$STATE/health"; printf 'PATH=/usr/bin\nUNSWEEP_CHAIN_ID=8453\nOPS_PK=x\n' > "$STATE/env" ;;
    *--build*) [ "${FAKE_BUILD_FAIL:-0}" = 1 ] && exit 1
               echo "$FAKE_BUILD_HEALTH" > "$STATE/health"; printf "$FAKE_BUILD_ENV" > "$STATE/env" ;;
  esac
fi
exit 0
'''

CURL_STUB = r'''#!/usr/bin/env bash
out=""; while [ $# -gt 0 ]; do [ "$1" = -o ] && out="$2"; shift; done
if [ "$(cat "$STATE/health")" = ok ]; then echo '{"ok":true,"chainId":8453,"mainnet":true}' > "$out"; printf 200
else echo '{"ok":false}' > "$out"; printf 503; fi
'''

def _exe(p, body):
    p.write_text(body); p.chmod(p.stat().st_mode | stat.S_IEXEC)

def _git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

@pytest.fixture
def env(tmp_path):
    st = tmp_path / "state"; st.mkdir()
    (st / "health").write_text("ok\n")
    (st / "env").write_text("PATH=/usr/bin\nOPS_PK=" + SECRET_VALUE + "\n")
    origin = tmp_path / "origin.git"; _git(tmp_path, "init", "-q", "--bare", str(origin))
    repo = tmp_path / "repo"; _git(tmp_path, "clone", "-q", str(origin), str(repo))
    _git(repo, "config", "user.email", "t@t"); _git(repo, "config", "user.name", "t")
    (repo / "deploy").mkdir(); (repo / "deploy/docker-compose.yml").write_text("name: t\n")
    _git(repo, "add", "-A"); _git(repo, "commit", "-qm", "base"); _git(repo, "push", "-q", "origin", "HEAD:refs/heads/main")
    (repo / "f.txt").write_text("v2\n"); _git(repo, "add", "-A"); _git(repo, "commit", "-qm", "v2")
    _git(repo, "push", "-q", "origin", "HEAD:refs/heads/nueva")
    target = _git(repo, "rev-parse", "HEAD"); _git(repo, "checkout", "-q", "HEAD~1")
    prev = _git(repo, "rev-parse", "HEAD")
    envf = tmp_path / "relayer.env"
    envf.write_text("# min\nTURNSTILE_SECRET=" + SECRET_VALUE + "\nOPS_PK=" + SECRET_VALUE + "\nBASE_RPC_URL=https://x\n"); envf.chmod(0o600)
    _exe(tmp_path / "docker", DOCKER_STUB); _exe(tmp_path / "curl", CURL_STUB)
    e = dict(os.environ, STATE=str(st), UNSWEEP_REPO=str(repo), UNSWEEP_ENV_FILE=str(envf),
             DOCKER=str(tmp_path / "docker"), CURL=str(tmp_path / "curl"), HEALTH_MAX="5", HEALTH_SLEEP="0",
             FAKE_BUILD_HEALTH="ok", FAKE_BUILD_ENV="PATH=/usr/bin\\nOPS_PK=x\\n")
    e.pop("_DR_COPY", None)
    return dict(e=e, st=st, repo=repo, envf=envf, target=target, prev=prev)

def run(env, *args, **extra):
    e = dict(env["e"], **extra)
    r = subprocess.run(["bash", str(SCRIPT), *args], env=e, capture_output=True, text=True, timeout=60)
    out = r.stdout + r.stderr
    assert SECRET_VALUE not in out, "el script imprimio un valor secreto"
    return r.returncode, out

def dlog(env):
    p = env["st"] / "docker.log"; return p.read_text() if p.exists() else ""

def head(env):
    return _git(env["repo"], "rev-parse", "HEAD")

def test_sha_invalido(env):
    rc, out = run(env, "--commit", "abc")
    assert rc == 1 and "40 hex" in out

def test_sha_no_publicado(env):
    rc, out = run(env, "--commit", "0" * 40)
    assert rc == 1 and head(env) == env["prev"]

def test_env_file_con_nombre_prohibido(env):
    env["envf"].write_text("OPS_PK=a\nPAYER_PK=" + SECRET_VALUE + "\n"); env["envf"].chmod(0o600)
    rc, out = run(env, "--commit", env["target"])
    assert rc == 1 and "PAYER_PK" in out and "compose" not in dlog(env)

def test_env_file_permisos(env):
    env["envf"].chmod(0o644)
    rc, out = run(env, "--commit", env["target"])
    assert rc == 1 and "600" in out

def test_dry_run_sin_cambios(env):
    rc, out = run(env, "--commit", env["target"], "--dry-run")
    assert rc == 0 and "DRY-RUN OK" in out
    assert head(env) == env["prev"]
    assert "compose" not in dlog(env) and "tag" not in dlog(env)

def test_despliegue_ok(env):
    rc, out = run(env, "--commit", env["target"])
    assert rc == 0 and "DESPLIEGUE OK" in out
    assert head(env) == env["target"]
    assert "compose -p unsweep" in dlog(env) and "--build --force-recreate relayer" in dlog(env)
    assert "secretos prohibidos en el contenedor: ninguno" in out

def test_health_falla_rollback(env):
    rc, out = run(env, "--commit", env["target"], FAKE_BUILD_HEALTH="bad")
    assert rc == 2 and "ROLLBACK OK" in out
    assert head(env) == env["prev"]
    assert "--no-build" in dlog(env)

def test_build_falla_rollback(env):
    rc, out = run(env, "--commit", env["target"], FAKE_BUILD_FAIL="1")
    assert rc == 2 and "ROLLBACK OK" in out and head(env) == env["prev"]

def test_secreto_en_contenedor_rollback(env):
    rc, out = run(env, "--commit", env["target"],
                  FAKE_BUILD_ENV="PATH=/usr/bin\\nGITHUB_TOKEN=" + SECRET_VALUE + "\\n")
    assert rc == 2 and "PROHIBIDA en el contenedor: GITHUB_TOKEN" in out and "ROLLBACK OK" in out
    assert head(env) == env["prev"]
