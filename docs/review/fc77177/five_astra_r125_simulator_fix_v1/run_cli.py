from __future__ import annotations
import os, subprocess, json
from pathlib import Path
ROOT=Path('/home/bigdata/Desktop/arknights-auto-planner')
BASE=ROOT/'docs/review/fc77177/five_astra_r125_simulator_fix_v1'
ATTEMPT=BASE/'session/codex_cli/attempt_01'
ATTEMPT.mkdir(parents=True,exist_ok=True)
PROMPT=BASE/'tactical_prompt_v1.txt'
CONFIG=BASE/'session_config_v1.json'
argv=[
 "timeout","3600s","codex","exec","--json","--sandbox","read-only",
 "--cd",str(ROOT),
 "-c",'model_provider="openai"',
 "-c","features.apps=false",
 "-c",f'mcp_servers.kimiark.command="{ROOT/".venv/bin/python"}"',
 "-c",f'mcp_servers.kimiark.args=["{BASE/"batch_service.py"}","{CONFIG}"]',
 "-c","mcp_servers.kimiark.required=true",
 "-c",'mcp_servers.kimiark.default_tools_approval_mode="approve"',
 "-c",'mcp_servers.kimiark.enabled_tools=["get_session_status","query_events","inspect_evidence"]',
 "-m","gpt-6.2-astra",
 "-c",'model_reasoning_effort="low"',
 "-o",str(ATTEMPT/"codex_final_message.txt"),
 "-",
]
env=dict(os.environ)
env.update({
 "HTTP_PROXY":"http://127.0.0.1:7890","HTTPS_PROXY":"http://127.0.0.1:7890",
 "ALL_PROXY":"socks5://127.0.0.1:7890","http_proxy":"http://127.0.0.1:7890",
 "https_proxy":"http://127.0.0.1:7890","all_proxy":"socks5://127.0.0.1:7890",
 "NO_PROXY":"localhost,127.0.0.1,::1","no_proxy":"localhost,127.0.0.1,::1",
 "CODEX_HOME":str(ROOT/".runtime/codex-home"),
})
(ATTEMPT/"codex_command.json").write_text(json.dumps({"argv":argv,"prompt_sha256":__import__("hashlib").sha256(PROMPT.read_bytes()).hexdigest(),"timeout_seconds":3600},indent=2)+"\n")
auth=json.loads((BASE/"model_authorization_v1.json").read_text())
auth["real_cli_starts"]["used_real_cli_starts"]=1
auth["real_cli_starts"]["attempt_1_status"]="STARTED_COUNTED"
(BASE/"model_authorization_v1.json").write_text(json.dumps(auth,ensure_ascii=False,indent=2)+"\n")
with (ATTEMPT/"codex_exec.jsonl").open("wb") as out,(ATTEMPT/"codex_stderr.txt").open("wb") as err,(PROMPT).open("rb") as inp:
 p=subprocess.Popen(argv,cwd=ROOT,stdin=inp,stdout=out,stderr=err,env=env)
 code=p.wait()
(ATTEMPT/"process_result.json").write_text(json.dumps({"exit_code":code},indent=2)+"\n")
print("exit",code)
