# Agent Operating Procedures
You are an autonomous coding agent operating within the Cursor IDE. 
1. **Context Awareness:** Always refer to `MINERVA_PIPELINE.md`, `RADIOMICS_LAYER_SPECS.md`, `RUN_CONTEXT.md`, and `NEXT_STEPS.md` before writing logic.
2. **Mandatory Logging:** Before executing shell commands or writing complex scripts, you MUST append a log entry to `agent_logs/action_log.md` detailing your intent, the target file, and the expected outcome.
3. **Deterministic First:** When writing the Vision Track, prioritize standard mathematical bounding-box logic (e.g., OpenCV, PIL) to verify VLM outputs. Do not rely blindly on the VLM.
4. **ReadME Update for Understanding Workflow:** After each change, update readme file `Readme.md` on what was changed, and keep a high level view of workflow, models being used, data inflow outflow, overall pipeline architecture.
5. **If applicable, update `pipeline_tracking.md` so that it stays on track for the end-to-end pipeline flow and critical configurations (final or latest used) input output flow, summarys in each step of the end-to-end pipeline. 
6. **Persistent Handoff:** Keep `docs/NEXT_STEPS.md` current whenever the primary operational priority, blocker, execution environment, or next milestone changes. This file is the required handoff for future local and GPU agents. It is not auto-generated; the active agent must update it as part of substantive progress.
7. **Direct Evidence Only:** Do not emit graph edges from within-paper bridge matches that only share a disease context. Such matches must be written as audit-only hypotheses and never ingested into Neo4j as asserted relationships.
