---
name: sciencepal
version: 0.6.0
description: "Run and manage SciencePal science-research agent sessions across stg + prd: start tasks, list/status/stop sessions, browse/upload/download sandbox files (biology, materials, protein, plasma, patents). Use for SciencePal tasks, managing your sessions across environments, checking agent runs, or sandbox files. NOT for general web or paper search."
---

# SciencePal

Science research agent platform with sandbox compute environments.

## Decision Tree

```
User request  (every script takes --env stg|prd, default stg)
+-- "send a message / start a task"     --> start.py -p "..."  (a SciencePal message = a new session)
+-- "follow up / answer its question"   --> followup.py -t <thread_id> -p "..."  (continue an EXISTING session)
+-- "list / manage my sessions"         --> sessions.py
+-- "check status / is it done"         --> status.py (one-shot or --wait)
+-- "stop a run"                        --> stop.py <agent_run_id>
+-- "download results"                  --> sandbox.py download <thread_id>
+-- "show/list/browse sandbox files"    --> sandbox.py ls <sandbox_id> <path>
+-- "read a sandbox file"              --> sandbox.py cat <sandbox_id> <path>
+-- "upload file to sandbox"           --> sandbox.py upload <sandbox_id> <local> <remote>
+-- "delete sandbox file"              --> sandbox.py rm <sandbox_id> <path>
```

## Scripts

All scripts run from this skill's `scripts/` folder: `uv run --no-project --with httpx python3 <script>`.

**Environments.** Every script takes `--env stg|prd` (default `stg`). Two credential sets live in `~/.zshenv.local` (gitignored): `SCIENCEPAL_{STG,PRD}_ACCESS_TOKEN` + `SCIENCEPAL_{STG,PRD}_BASE_URL` (stg = `https://stg.sciencepal.ai/api`, prd = `https://sciencepal.ai/api`). Tokens are short-lived Supabase JWTs — on a 401 the script prints a refresh hint; log into the web app, copy a fresh token, update the var. SciencePal runs sessions **concurrently** (each is its own project + sandbox), so you can start and manage several at once.

### start.py -- Start a run

```bash
python3 start.py -p "user question"
# -> {thread_id, agent_run_id}
python3 start.py -p "..." --timeout 600     # raise the initiate wait further
```

Print both IDs immediately.
User needs them for status checks and downloads.

**A timeout here is not a failure.** `/agent/initiate` provisions a sandbox before it answers, so it is far slower than every other endpoint; the wait defaults to 300s for this call alone, against 60s everywhere else. If it still times out, the run has almost certainly started anyway and the server keeps going after the client gives up. Do NOT re-run the command, which starts a SECOND run: find the new session with `sessions.py` instead, as the newest entry in status `initializing` or `running`. Measured 2026-08-20 on both environments: three calls that timed out at the old shared 60s each still created a session (stg 153 to 155 over two calls, prd 118 to 119 over one), and the same prompt succeeded on the first try once the wait was raised.

Read the exit code, do not guess from the message. **Exit 2** = request sent, no usable response, so a run probably exists and you must go find it. **Exit 3** = the API was never reached, so nothing started and retrying is safe. Connect is capped at 10s regardless of `--timeout`, so exit 3 arrives quickly.

### followup.py -- Continue an existing session

```bash
python3 followup.py -t <thread_id> -p "answer or steering text"   # insert message + start agent
python3 followup.py -t <thread_id> -p "..." --no-start            # queue message only
# -> {agent_run_id, status, thread_id}
```

THE way to answer an agent's clarifying questions (the brainstorming gate holds one-shot runs until answered) or steer/continue a finished session. Two-step wire protocol mirroring the web frontend: PostgREST message insert (needs `SCIENCEPAL_{STG,PRD}_SUPABASE_ANON_KEY` in `~/.zshenv.local`; RLS limits inserts to threads the token's user owns) then `POST /thread/{id}/agent/start`. Note: the backend API tolerates expired JWTs but Supabase does not — a 401 here with a "working" token means the token is time-expired; refresh it.

### status.py -- Check or wait for status

```bash
python3 status.py <agent_run_id>          # one-shot check
python3 status.py <agent_run_id> --wait   # poll until terminal
```

Terminal statuses: `completed`, `failed`, `stopped`.

### sessions.py -- List / manage all sessions

```bash
python3 sessions.py --env prd           # list the account's projects + run statuses
python3 sessions.py --env stg --json    # raw JSON
```

The entry point for "manage all my sessions" — see what's running/done across the account, then act on a specific run with status.py / stop.py / sandbox.py.

### stop.py -- Stop a run

```bash
python3 stop.py <agent_run_id> --env prd
```

### sandbox.py -- Sandbox file operations

```bash
python3 sandbox.py ls <sandbox_id> /workspace
python3 sandbox.py cat <sandbox_id> /workspace/report.md
python3 sandbox.py download <thread_id> -o <output-dir>/sciencepal/<run_id>/
python3 sandbox.py upload <sandbox_id> local.pdb /workspace/input.pdb
python3 sandbox.py rm <sandbox_id> /workspace/tmp.txt
```

`download` takes thread_id (resolves sandbox automatically).
All other subcommands take sandbox_id directly.

## Domain-Specific Prompt Engineering

Prompt quality determines result quality.
Generic prompts produce generic results; domain-tuned prompts activate the agent's specialized tools and knowledge.

### Biology / Genomics

- Specify organism, gene names with standard nomenclature (HGNC symbols for human, e.g., TP53 not p53).
- Include the biological context: "in the context of pancreatic ductal adenocarcinoma" not just "cancer".
- Request specific output formats: "provide a pathway diagram" or "list differentially expressed genes with log2FC and adjusted p-value".
- Common failure: vague prompts like "analyze this gene" -- the agent has no idea which analysis (expression, variants, interactions, pathways).

### Protein / Structural Biology

- Input MUST be PDB format or UniProt accession (e.g., P04637) -- FASTA alone is insufficient for structural tasks.
- Specify the task precisely: "predict binding affinity" vs "dock these two proteins" vs "identify active site residues".
- For folding tasks, include template PDB IDs if homologs exist -- the agent uses them for refinement.
- Common failure: uploading sequences without specifying chain IDs or ligands of interest.

### Materials Science

- Use standard composition notation: chemical formulas (Li2FePO4, not "lithium iron phosphate") and space groups (Fm-3m).
- Specify target properties: "band gap > 2 eV" or "thermal conductivity at 300K".
- Include synthesis constraints if relevant: "solution-processable" or "stable above 500C".
- Common failure: describing materials in natural language instead of composition -- the agent's tools expect structured chemical input.

### Patent Analysis

- Provide patent numbers in standard format (US20230001234A1, CN115000000B).
- Specify jurisdiction when relevant -- patent law varies by country.
- For landscape analysis, provide seed patents or CPC/IPC classification codes rather than broad topic descriptions.

## One-Shot Execution and the Clarify-Gate

By default a fresh task does NOT run to completion in one shot. The agent routes through a `brainstorming` skill whose hard-gate forbids any research execution until the user confirms a plan -- so even a fully-specified prompt triggers one round of clarifying questions and the run parks in the `asked` state (awaiting user input), never reaching `completed`.

Two ways to get a true one-shot run:

1. **Answer the clarifying questions** -- send a follow-up user message, then the agent proceeds.
2. **Pre-empt the gate with a directive prompt** -- state every parameter the agent would otherwise ask about, and explicitly instruct it not to ask. This skips the clarify round; the run proceeds straight to execution and on to `completed`.

Directive prompt template (verified to bypass the gate):

```
请直接执行以下研究任务，全程自主完成，无需提问、无需确认计划——范围参数已在下方给出。
任务：<一句话目标>
已明确（无需再询问）：对象/体系、维度、文献年份窗口、允许的方法（检索/解析/抓取）、输出语言。
交付物（保存到 /workspace）：report.md（带引文）、<图/表规格>、<数据表列含 DOI/PMID>。
请直接开始，不要提问，完成后给出交付物清单与简要总结。
```

Dimensions to pre-answer (these are what the agent asks about): object/system scope, which mechanism dimensions, literature year-window, whether web-scraping is allowed, output language and format, deliverable granularity.

## /loop Prompt Design

A `/loop` message drives a session across ticks.
Commands are dispatched only on the insert-then-start path, so arm a loop with `followup.py -t <thread_id> -p "/loop ..."`; `start.py` alone will not arm one.

- `/loop <interval> <prompt>` -- interval mode, re-ticks on a fixed interval (floor 60s). The working form.
- `/loop <prompt>` with no interval -- self-paced mode, **refused at dispatch**: it replies `{"loop": "rejected"}` and arms nothing (no loop cleared, no run enqueued).
  A self-paced tick cannot schedule its own successor while the current run is still active, so it would arm and never fire.
  Treat the mode as unavailable; always pass an interval.
- `/loop stop` -- deterministic clear; already-queued ticks are cancelled, not just the next one.

Any other human turn also clears an armed loop. `/compact` does not, and neither does stopping the current agent run.
From inside a tick the agent can end the loop itself by calling the `stop_loop` tool; that is what makes a "loop until X" instruction terminate instead of running to the 100-tick cap.

**Rule: every loop prompt must be a self-contained directive.** A tick runs unattended -- if its prompt trips the clarify-gate it parks in `asked` and the loop cannot answer itself, so the whole loop stalls. Always include "do not ask, complete autonomously".

**Rule: give the loop its own exit.** Every prompt states a completion condition and instructs the agent to call `stop_loop` when it is met; an interval loop with no exit runs to the cap.

**Rule: consistency is a fine exit for a survey and a poor one for a number.** An exit built on internal consistency, or on agreement between paths the agent re-derived itself, is sound against arithmetic slips and unstable fits and worthless against an error in a model specification that every path shares. Agreement is what fires the stop, so a shared specification error is the one class that ends the search *early*, and it arrives with a cross-checked audit trail that makes the wrong number look more trustworthy the harder it was verified. Measured on a quantitative benchmark task: four derivation paths differing in estimator converged inside a 0.044-wide band, all of them the wrong sign, and that agreement triggered `stop_loop`. When the deliverable is quantitative, the exit needs at least one check that does not inherit the primary model's assumptions: a quantity the data determines directly, a control the task itself supplies, a bound from a different measurement channel, or a sign predicted before fitting.

Four patterns:

- **Drive-to-complete** (best for finishing a large task autonomously): `/loop 10m 自主推进直至完成，全程不要提问：每轮检索新文献、更新综述/图/表，补全上轮空缺；当覆盖全面、引文齐全且前后一致时，调用 stop_loop 结束循环并输出 /workspace 交付物。`
- **Interval monitoring** (ongoing literature surveillance): `/loop 24h 检索过去24小时新论文，不要提问：有则更新并追加到 /workspace/updates.md，无则记录"无更新"。`
- **Bounded refinement** (fixed number of passes): `/loop 30m 共3轮精炼，不要提问：第1轮补机制、第2轮补定量数据、第3轮校验引文与一致性；每轮存版本；第3轮结束后调用 stop_loop。`
- **Quantitative deliverable** (the exit must not rest on self-agreement): `/loop 15m 自主推进直至完成，全程不要提问：每轮除主结果外，另跑一条不共享主模型假设的独立校验（数据直接决定的量、任务自带的对照、另一测量通道的界、拟合前预先给出的符号）；只有当该独立校验与主结果一致、且本轮无实质变化时，才调用 stop_loop；若两者不一致，本轮不得结束，改为记录分歧并检查主模型设定。`

## /compact

`/compact [focus hint]` on the same insert-then-start path compresses a long session into a research-resumption summary.
It starts no agent run, and it does not clear an armed loop.
Every summary is also written to the thread's sandbox at `/workspace/compact/<yyyy_mmdd_hhmmss>.md` (the response carries `summary_file`), so it is readable with the ordinary sandbox file commands.
Archiving is best-effort: if the sandbox is unavailable the compaction still succeeds and `summary_file` comes back null.

## Result Quality Signals

After downloading results, verify quality before reporting to user:

| Signal                | Good result                                      | Suspect result                               |
| --------------------- | ------------------------------------------------ | -------------------------------------------- |
| Citations             | Cites specific papers with DOIs or PMIDs         | No citations, or only cites reviews          |
| Methodology           | Describes tools/databases used (BLAST, PDB, MP)  | Vague "analysis was performed"               |
| Reproducibility       | Lists parameters, versions, input files          | No method details, just conclusions          |
| Quantitative results  | Includes numbers with units and confidence       | Only qualitative statements                  |
| Data files            | Contains raw data files matching the analysis    | Report only, no supporting data              |
| Internal consistency  | Figures match text, numbers add up               | Contradictions between sections              |

If results show suspect signals, the agent likely hallucinated or used shallow analysis.
Re-run with a more constrained prompt that forces tool usage (e.g., "use BLAST to search against UniProt" instead of "find similar proteins").

## Agent Orchestration Patterns

### Task Decomposition

SciencePal agents handle multi-step scientific workflows internally.
The user provides a high-level research question; the agent decomposes it into sub-tasks (literature search, data retrieval, analysis, synthesis).
Do not attempt to manually orchestrate sub-steps -- let the agent handle decomposition.

### When to Decompose Manually vs Let the Agent Handle It

Let the agent handle decomposition when:
- The question is within a single domain (e.g., "find proteins that interact with BRCA1").
- The expected output is a single report or dataset.

Break into sub-tasks manually when:
- The workflow crosses domains (e.g., literature review on material properties -> formulate synthesis hypothesis -> design experiment protocol).
- You need to inspect intermediate results before proceeding (e.g., verify a gene list before running pathway enrichment).
- The task would exceed sandbox memory or time limits as a single run.

### Sequential Pipeline Pattern

Run tasks in sequence, using outputs to inform next steps:

1. **Literature review**: `start.py -p "survey recent methods for X"` -- download report, extract key findings.
2. **Hypothesis formulation**: `start.py -p "given these findings: [paste key points], propose testable hypotheses for Y"`.
3. **Experiment design**: `start.py -p "design an experiment to test hypothesis Z, using methods A and B"`.

Between each step: download results, read the report, extract the relevant findings to include in the next prompt.

### Parallel Exploration Pattern

Run the same question with different framings to compare approaches:

- `start.py -p "analyze protein X using molecular dynamics simulation"` (run 1)
- `start.py -p "analyze protein X using homology modeling and docking"` (run 2)

Compare results after both complete.
Use this when the best methodology is unclear or when the user wants to evaluate multiple approaches.

### Long-Running Tasks

Science tasks often take 5-30 minutes.
After starting a run, use `status.py --wait` to poll automatically rather than checking manually in a loop.
If the user needs to do other work, report the run IDs and offer to check later.

### Result Interpretation

Downloaded results land in `/workspace` inside the sandbox.
Common output patterns:
- `report.md` or `summary.md` -- main findings.
- `data/` -- raw or processed data files.
- `figures/` -- generated plots or visualizations.

Read the report file first to understand what the agent produced, then examine data files as needed.

## Error Recovery

### General Recovery

If a run fails:
1. Check the status output for error messages.
2. Review sandbox files for partial results (`sandbox.py ls`).
3. Reformulate the prompt with more specific constraints and restart.

Sandbox auto-stops after 10 minutes of idle time.
If returning to a completed run after a delay, call `ensure-active` before accessing files.

### Domain-Specific Recovery

| Problem                              | Likely cause                          | Fix                                                                     |
| ------------------------------------ | ------------------------------------- | ----------------------------------------------------------------------- |
| Agent produced irrelevant results    | Prompt too broad or ambiguous         | Narrow the domain, specify organism/material/method explicitly          |
| Sandbox ran out of memory            | Dataset too large for sandbox         | Reduce input size, request streaming/chunked processing, or subset data |
| Results contradict known literature  | Agent hallucinated or used wrong tool | Verify key claims against cited sources; re-run with explicit tool use  |
| PDB parsing errors                   | Wrong format or missing chain IDs     | Validate PDB file locally before upload; specify chain explicitly       |
| No data files in output              | Agent wrote report without running tools | Re-prompt: "you must run [specific tool] and save raw output"        |
| Agent stuck in literature review     | Question too open-ended               | Constrain: "focus only on papers from 2020-2024 about X"               |

## API Reference

**LOAD [`references/api.md`](references/api.md) when you need endpoint details, request/response formats, or query parameters.**

Do NOT load for routine script usage -- the scripts handle API calls internally.

## NEVER

- NEVER send JSON body to `/agent/initiate` -- it requires **form-data**. JSON returns 422.
- NEVER retry `start.py` after a timeout -- the run is already live server-side, so a retry starts a second one. Locate it with `sessions.py`.
- NEVER assume sandbox is alive -- it auto-stops after 10min idle. Call `ensure-active` first if the run finished a while ago.
- NEVER download from a `failed` or `stopped` run -- sandbox may have incomplete/corrupt state.
- NEVER put downloaded files inside a project repo -- use a scratch directory outside it, such as `<output-dir>/sciencepal/<run_id>/`, or the project's own data directory.
- NEVER poll status faster than every 10 seconds -- respect rate limits.
- NEVER expose or log the `SCIENCEPAL_ACCESS_TOKEN` value.

## Error Handling

| Error                     | Cause                                   | Fix                                     |
| ------------------------- | --------------------------------------- | --------------------------------------- |
| 401 Unauthorized          | Token expired or invalid                | Refresh token at sciencepal.ai          |
| 404 on `/agent-run/{id}`  | Invalid run ID                          | Check ID from start.py output           |
| 404 on sandbox file read  | File doesn't exist or sandbox destroyed | Try `sandbox.py ls` first to verify     |
| 422 on `/agent/initiate`  | Sent JSON instead of form-data          | Scripts handle this correctly           |
| Timeout on `start.py`     | Sandbox provisioning outran the wait    | Run IS live; find it via `sessions.py`, never retry |
| 500 on sandbox operations | Sandbox crashed or being archived       | Call `ensure-active`, retry             |
| Timeout on `--wait`       | Task taking too long                    | Check status manually, increase timeout |

## Rules

- Print `thread_id` and `agent_run_id` immediately after starting.
- Output files go to `<output-dir>/sciencepal/<run_id>/` or the project's data dir, not inside any project repo.
- Agent task results are in `/workspace` inside the sandbox.
- Tool/model files live in `/app` -- these are read-only base image contents, not task outputs.
