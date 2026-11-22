"""#1195 v12g: --service relayer|relayer-arb y --plan de deploy/deploy_relayer.sh (sin red ni Docker real)."""
import os, subprocess, pathlib

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "deploy_relayer.sh"
SHA = "a" * 40


def _env(tmp_path, **kw):
    st = tmp_path / "state"; st.mkdir(exist_ok=True)
    d = tmp_path / "docker"
    d.write_text('#!/usr/bin/env bash\necho "$*" >> "$STATE/docker.log"\nexit 1\n'); d.chmod(0o755)
    e = dict(os.environ, STATE=str(st), DOCKER=str(d), CURL="/bin/false")
    e.update({k: str(v) for k, v in kw.items()})
    return e, st


def _run(args, env):
    return subprocess.run(["bash", str(SCRIPT)] + args, env=env, capture_output=True, text=True, timeout=60)


def test_plan_imprime_ambos_servicios_sin_ejecutar(tmp_path):
    e, st = _env(tmp_path, UNSWEEP_REPO=tmp_path / "base", UNSWEEP_ARB_REPO=tmp_path / "arb")
    r = _run(["--plan"], e)
    assert r.returncode == 0, r.stderr
    assert "PLAN service=relayer CONTAINER=unsweep-relayer IMAGE=unsweep-relayer:latest compose_svc=relayer" in r.stdout
    assert "chainId=8453" in r.stdout and "HEALTH_URL=https://unsweep.com/api/health" in r.stdout
    assert "PLAN service=relayer-arb CONTAINER=unsweep-relayer-arb IMAGE=unsweep-relayer-arb:latest compose_svc=relayer-arb" in r.stdout
    assert "chainId=42161" in r.stdout and "PLAN OK: nada ejecutado" in r.stdout
    assert not (st / "docker.log").exists()


def test_arb_rechaza_repo_de_base(tmp_path):
    base = tmp_path / "base"; base.mkdir()
    e, st = _env(tmp_path, UNSWEEP_REPO=base, UNSWEEP_ARB_REPO=base)
    r = _run(["--commit", SHA, "--service", "relayer-arb", "--dry-run"], e)
    assert r.returncode == 1 and "no puede usar el REPO de Base" in r.stderr
    assert not (st / "docker.log").exists()


def test_service_invalido(tmp_path):
    e, _ = _env(tmp_path)
    r = _run(["--commit", SHA, "--service", "otro"], e)
    assert r.returncode == 1 and "--service debe ser relayer o relayer-arb" in r.stderr


def test_arb_repo_inexistente(tmp_path):
    e, st = _env(tmp_path, UNSWEEP_REPO=tmp_path / "base", UNSWEEP_ARB_REPO=tmp_path / "noexiste")
    r = _run(["--commit", SHA, "--service", "relayer-arb", "--dry-run"], e)
    assert r.returncode == 1 and "REPO arb inexistente" in r.stderr
    assert not (st / "docker.log").exists()
