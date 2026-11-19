# R121 固定五人五轮

克洛丝/月见夜/史都华德/芙蓉/翎羽。无完整WIN。最佳040独立复验11杀22漏、双保护到达、零剩余、炮兵仍漏。

- RESULT_TO_COPY.txt：简短交付；BEST_AXIS_TO_COPY.tsv：最佳21动作完整可复制轴。
- closeout_v1.md/.json、best_selection_v1.json、round_results_v1.json：结果、五轮证据和真实计数。
- parent_registry_v1.json、sealed_ledger_hashes.json、batch_constraints.json：参考原件、固定名单和预算来源。
- actual_model_search_requests.json、actual_model_round_records.json、model_provenance_verification.json：真实单一Astra决策、所有PASS由其原参数重建。
- recorded_fifth_round_execution.json、execute_recorded_fifth_round.py：Astra已提交但遭宿主误停的原8组，模型退出后仅机械补执行；原始失败/final保留。
- final_reverification_selection.json、final_reverification_execution.json：执行端按严格结果支配选择040真实复验，非伪称Astra新决策。
- session/codex_cli/、session/candidates/、reverification/：原始会话、候选、两次独立复跑。039为计账执行前失败，无真实战斗。
- key_event_index_v1.json、best_frozen_plan.json、best_action_timeline.json：原始关键事件与冻结最佳计划。
- artifact_manifest_v1.json、gzip_archive_v1.json、archive_verification_v1.json：全文件hash、gzip逻辑路径映射及还原核验。

已封存，禁止重跑prepare/run_cli或补执行程序续开本批；finalize/export_results/archive/verify仅派生解析归档不战斗。所有引用.json/.jsonl若已压缩按gzip映射读。旧账本保持，不推送。
