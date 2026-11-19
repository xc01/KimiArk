# R118 独立 Astra 七人闭环

已结束：五轮，一个真实 gpt-6.2-astra / low CLI，24 check、18 PASS 候选、19 完整固定模拟（含独立复验）。未取得七人完整 WIN。

- closeout_v1.md：结项、五轮、原始事件对照、未执行问题。
- closeout_v1.json、final_budget_v1.json：机器结果及封存计数。
- parent_registry_v1.json、sealed_ledger_hashes.json：A/B/C/D 原件及旧封存记录。
- model_provenance_verification.json：18 候选由真实模型工具参数重建的深度相等证明。
- actual_model_search_requests.json、actual_model_round_records.json：真实 Astra 可见决策。
- best_canonical_action_diff.json、extra_damage_comparison.json、key_event_index_v1.json：单字段变化与事件证据。
- session/codex_cli/：真实命令、冻结输入 hash、原始轨迹、最终消息和进程计量。
- session/candidates/、reverification/independent-1/：生产原件及真实独立复跑。
- gzip_archive_v1.json、artifact_manifest_v1.json、archive_verification_v1.json：逻辑路径到 gzip 物理路径、压缩及还原 hash、归档复核。

本批封存。prepare.py、preflight.py、run_cli.py 仅保存实际程序，不得重跑以重置或续跑本批。finalize.py、archive_batch.py、verify_archive.py 只核验/归档，不产生战斗。日志的逻辑原路径可经 gzip 映射读取，prepare.read 支持 JSON 归档回退。
