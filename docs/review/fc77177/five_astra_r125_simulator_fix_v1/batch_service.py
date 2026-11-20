"""R125 read-only evidence transport: no tactical candidates or simulations."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path('/home/bigdata/Desktop/arknights-auto-planner')
BASE=ROOT/'docs/review/fc77177/five_astra_r125_simulator_fix_v1'
sys.path.insert(0,str(ROOT/'scripts'))
import kimiark_tactical_stdio_service_v1 as production
from kimiark_tactical_stdio_service_v1 import SessionConfig, load_session_config, handle_message

TOOLS=[
 {"name":"get_session_status","description":"Read-only ledger/status snapshot for R125.","inputSchema":{"type":"object","properties":{}}},
 {"name":"query_events","description":"Read-only paged event query for archived R8-7 candidates (query_events contract).","inputSchema":{"type":"object","properties":{"candidate_id":{"type":"string"},"event_type":{"type":"string"},"frame":{"type":"object"},"offset":{"type":"integer"},"limit":{"type":"integer"},"aggregate":{"type":"object"}}}},
 {"name":"inspect_evidence","description":"Read-only R125 evidence inspector: gaps, kb entries, code snippets, prior events.","inputSchema":{"type":"object","properties":{"kind":{"type":"string"},"path":{"type":"string"},"line":{"type":"integer"},"limit":{"type":"integer"},"candidate_id":{"type":"string"},"event_type":{"type":"string"},"offset":{"type":"integer"},"limit":{"type":"integer"}}}},
]

def _read_json(path:Path):
 if not path.exists():
  raise RuntimeError(f'missing file: {path}')
 return production.json.loads(path.read_text())

def _load_evidence():
 return _read_json(BASE/'input_bundle/llm_evidence_context.json')

def session_status_ro(config:SessionConfig):
 status=production.session_status(config)
 status["scope"]="R125_SIMULATOR_FIX_READ_ONLY"
 status["no_tactical_candidates_or_simulations"]=True
 return status

def inspect_evidence_ro(config:SessionConfig,a:dict):
 kind=a.get("kind","context")
 if kind=="context":
  return _load_evidence()
 if kind=="code":
  p=(ROOT/a["path"]).resolve()
  p.relative_to(ROOT)
  if not p.is_file() or p.suffix not in {".py",".json",".md"}:
   raise RuntimeError("read-only code path invalid")
  lines=p.read_text().splitlines()
  start=max(0,int(a.get("line",1))-1)
  n=min(int(a.get("limit",120)),200)
  return {"path":str(p.relative_to(ROOT)),"first_line":start+1,"lines":lines[start:start+n],
          "sha256":production.hashlib.sha256(p.read_bytes()).hexdigest()}
 if kind=="events":
  return production.query_events(config,a)
 raise RuntimeError(f"unknown inspect kind: {kind}")

def handle_message_ro(config:SessionConfig,message:dict):
 method=message.get("method")
 request_id=message.get("id")
 if method=="initialize":
  v=(message.get("params") or {}).get("protocolVersion")
  return {"jsonrpc":"2.0","id":request_id,"result":{"protocolVersion":v if isinstance(v,str) and v else production.PROTOCOL_VERSION,"serverInfo":{"name":"kimiark-r125-read-only","version":"1.0.0"},"capabilities":{"tools":{"listChanged":False}}}}
 if method=="tools/list":
  return {"jsonrpc":"2.0","id":request_id,"result":{"tools":TOOLS}}
 if method=="tools/call":
  name=(message.get("params") or {}).get("name")
  arguments=(message.get("params") or {}).get("arguments") or {}
  if name not in {"get_session_status","query_events","inspect_evidence"}:
   return {"jsonrpc":"2.0","id":request_id,"error":{"code":-32602,"message":"tool not enabled in R125 read-only scope"}}
  try:
   if name=="get_session_status": result=session_status_ro(config)
   elif name=="query_events": result=production.query_events(config,arguments)
   else: result=inspect_evidence_ro(config,arguments)
   return production.tool_result(result)
  except Exception as exc:
   return {"jsonrpc":"2.0","id":request_id,"result":production.tool_result({"ok":False,"error":repr(exc)})}
 if method in {"notifications/initialized","notifications/cancelled"} or method=="ping":
  return production.handle_message(config,message)
 return {"jsonrpc":"2.0","id":request_id,"error":{"code":-32601,"message":"method not found"}}

def main():
 import argparse
 parser=argparse.ArgumentParser()
 parser.add_argument("config")
 args=parser.parse_args()
 config=load_session_config(Path(args.config))
 for line in sys.stdin:
  if not line.strip():continue
  try:
   msg=production.json.loads(line)
  except production.json.JSONDecodeError as exc:
   resp={"jsonrpc":"2.0","id":None,"error":{"code":-32700,"message":f"Parse error: {exc}"}}
  else:
   resp=handle_message_ro(config,msg)
  if resp is not None:
   print(production.json.dumps(resp,ensure_ascii=False,separators=(",",":")),flush=True)

if __name__=="__main__":
 main()
