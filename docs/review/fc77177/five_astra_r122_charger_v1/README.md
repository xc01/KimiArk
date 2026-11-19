# R122 翎羽机制修复后五人五轮

机制m39新增亲自击杀+1DP、主动撤退返初始部署费。41项相关测试通过。五轮无完整WIN，最佳023独立复验12/21、双保护到达，相对原轴实救#28且无新增漏。

- RESULT_TO_COPY.txt：简短交付；BEST_AXIS_TO_COPY.tsv：完整21动作可复制轴。
- closeout_v1.md/.json、final_budget_v1.json：结果、五轮证据和用量。
- mechanic_patch_identity.json、mechanic_tests.txt：机制源码hash及测试。
- baseline_replay_comparison.json：旧040/011精确动作m39复跑、关键事件同轴、回费真实变化及父项ID瑕疵。
- actual_model_search_requests.json、actual_model_direct_submissions.json、actual_model_round_records.json、model_provenance_verification.json：真实单一Astra决策和32候选来源证明。
- best_action_diff.json、best_selection_v1.json、key_event_index_v1.json：最佳联动、原始事件、DP收入与限制。
- session/、reverification/independent-1/：生产原件、真实模型输出与独立复验。
- artifact_manifest_v1.json、gzip_archive_v1.json、archive_verification_v1.json：压缩路径及压缩/还原hash。

本批封存，不重跑prepare/run_cli或生产执行续跑；finalize/export/archive/verify只派生核验无战斗。旧版本档案保留，不伪称当前机制结论；不推送。
