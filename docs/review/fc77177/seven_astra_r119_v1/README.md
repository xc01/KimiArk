# R119 独立 Astra 七人闭环

已完成五轮，1个真实gpt-6.2-astra/low CLI、16check、12PASS候选、13完整固定模拟（含独立复验）；无完整七人WIN。

- RESULT_TO_COPY.txt：可直接复制的简短交付。
- closeout_v1.md / .json、final_budget_v1.json：事实结项和封存计数。
- zero_sim_priority_v1.md / .json：四漏敌人最后受击、可还原HP、实际目标选择与芬的阻挡/回费职责。
- parent_registry_v1.json、sealed_ledger_hashes.json：A/B/C/D/E冻结原件与旧账本。
- actual_model_search_requests.json、actual_model_round_records.json、model_provenance_verification.json：真实Astra决策和12候选机械重建证明。
- retained_action_diffs_v1.json、key_event_index_v1.json、healing_and_artillery_comparison_v1.json：保留分支差异与逐事件证据。
- session/codex_cli/、session/candidates/、reverification/independent-1/：原始会话、冻结候选、真实独立复跑。
- artifact_manifest_v1.json、gzip_archive_v1.json、archive_verification_v1.json：物理路径、压缩与还原hash、最终审计。

已封存，不重跑prepare/preflight/run_cli或生产工具以续跑本批。zero_sim_audit/finalize/archive_batch/verify_archive仅解析或归档，不产生新战斗。逻辑.json/.jsonl引用按gzip映射读取；旧原件及账本保持不动。
