from __future__ import annotations
import sys, os, subprocess, time, json, fcntl, hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/home/bigdata/Desktop/arknights-auto-planner')
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
import run_r8_1_gpt_c4_codex_cli_v1 as runtime

# --- Fix 1: auth. The inherited ~/.codex/auth.json holds a revoked OAuth token
# (token_revoked). The runtime home holds a valid token. Force CODEX_HOME there.
RUNTIME_HOME = ROOT / '.runtime/codex-home'
MODEL = 'gpt-6-astra'  # live catalog slug for GPT-6-Astra; legacy gpt-6.2-astra removed


def codex_environment() -> dict[str, str]:
    env = runtime.codex_environment()
    if not (RUNTIME_HOME / 'auth.json').is_file():
        raise RuntimeError(f'missing auth.json in {RUNTIME_HOME}')
    env['CODEX_HOME'] = str(RUNTIME_HOME)
    return env


def model_preflight(env: dict[str, str]) -> dict:
    """Zero-generation check: confirm the configured slug is advertised by the live catalog."""
    proc = subprocess.run(
        ['codex', '-m', MODEL, 'debug', 'models'],
        capture_output=True, text=True, env=env, cwd=ROOT, timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(f'model preflight failed rc={proc.returncode}: {proc.stderr[-800:]}')
    catalog = json.loads(proc.stdout)
    slugs = [m['slug'] for m in catalog['models']]
    if MODEL not in slugs:
        raise RuntimeError(f'model {MODEL!r} not in live catalog: {slugs}')
    record = {
        'schema_version': 'CODEX_MODEL_PREFLIGHT_V1',
        'model': MODEL,
        'catalog_slugs': slugs,
        'catalog_sha256': hashlib.sha256(proc.stdout.encode()).hexdigest(),
        'counts_as_model_generation': False,
        'counts_as_cli_start': False,
        'checked_at': datetime.now(timezone.utc).isoformat(),
    }
    (BASE / 'model_directory_verification.json').write_text(json.dumps(record, indent=1))
    return record


def main():
    out = BASE / 'session/codex_cli'
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'runner.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempt = out / 'cli_process_attempt.json'
        if attempt.exists():
            raise RuntimeError('CLI already attempted in this batch; no restart')
        env = codex_environment()
        preflight = model_preflight(env)
        prompt = (BASE / 'tactical_prompt.txt').read_text()
        last = out / 'codex_final_message.txt'
        command = [
            'codex', 'exec', '--json', '--sandbox', 'read-only', '--cd', str(ROOT),
            '-c', 'model_provider="openai"', '-c', 'features.apps=false',
            '-c', f'mcp_servers.kimiark.command="{ROOT/".venv/bin/python"}"',
            '-c', f'mcp_servers.kimiark.args=["{BASE/"batch_service.py"}","{BASE/"session_config_v1.json"}"]',
            '-c', 'mcp_servers.kimiark.tool_timeout_sec=1800',
            '-c', 'mcp_servers.kimiark.required=true',
            '-c', 'mcp_servers.kimiark.default_tools_approval_mode="approve"',
            '-c', 'mcp_servers.kimiark.enabled_tools=["get_session_status","list_parents","run_simulation","query_events","inspect_file"]',
            '-m', MODEL, '-c', 'model_reasoning_effort="low"',
            '-o', str(last), '-',
        ]
        (out / 'codex_prompt.txt').write_text(prompt)
        (out / 'codex_command.json').write_text(json.dumps({
            'argv': command, 'cwd': str(ROOT),
            'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
            'codex_home': str(RUNTIME_HOME),
            'automatic_retry': False, 'automatic_resume': False,
            'model_preflight': preflight,
        }, indent=1))
        attempt.write_text(json.dumps({
            'status': 'STARTED', 'time': datetime.now(timezone.utc).isoformat(),
            'model': MODEL, 'effort': 'low', 'attempted_cli_starts': 1,
            'codex_home': str(RUNTIME_HOME),
            'internal_model_request_count': 'UNKNOWN_CLI_INTERNAL',
            'automatic_retry': False, 'automatic_resume': False,
            'unlimited_simulations': True,
        }, indent=1))
        with (out / 'codex_exec.jsonl').open('w') as so, (out / 'codex_stderr.txt').open('w') as se:
            started = time.monotonic()
            p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=so, stderr=se,
                                 text=True, env=env, cwd=ROOT)
            (out / 'process_identity.json').write_text(json.dumps({
                'pid': p.pid, 'started_at': datetime.now(timezone.utc).isoformat(),
                'model': MODEL, 'effort': 'low'}, indent=1))
            p.stdin.write(prompt); p.stdin.close()
            failure = None
            while p.poll() is None:
                time.sleep(2)
                if time.monotonic() - started > 10800:
                    failure = {'reason': 'WALLTIME_10800_SECONDS'}; p.terminate(); break
            try:
                code = p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                p.kill(); code = p.wait()
        summary = runtime.extract_events_summary((out / 'codex_exec.jsonl').read_text())
        r = {'status': 'BLOCKED' if failure else ('COMPLETED' if code == 0 else 'FAILED'),
             'exit_code': code, 'failure': failure,
             'duration_seconds': round(time.monotonic() - started, 1),
             'cli_starts': 1, 'usage_records': summary.get('usage_records', []),
             'internal_model_requests': 'UNKNOWN_CLI_INTERNAL'}
        (out / 'cli_process_result.json').write_text(json.dumps(r, ensure_ascii=False, indent=1))
        print(json.dumps(r, ensure_ascii=False))


if __name__ == '__main__':
    main()
