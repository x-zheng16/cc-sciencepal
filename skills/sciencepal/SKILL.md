---
name: sciencepal
version: 0.2.0
description: >-
  Run SciencePal science research agents and manage sandbox environments.
  Use when user mentions SciencePal, or wants to start a science research task (biology, material, protein, plasma, patent analysis),
  check agent run status, or browse, download, upload, and delete files in a SciencePal sandbox.
  Do NOT use for general web search, paper search, or non-SciencePal tasks.
---

# SciencePal

Science research agent platform with sandbox compute environments.

## Decision Tree

```
User request
+-- "run/start/analyze with SciencePal" --> start.py
+-- "check status / is it done"         --> status.py (one-shot or --wait)
+-- "download results"                  --> sandbox.py download <thread_id>
+-- "show/list/browse sandbox files"    --> sandbox.py ls <sandbox_id> <path>
+-- "read a sandbox file"              --> sandbox.py cat <sandbox_id> <path>
+-- "upload file to sandbox"           --> sandbox.py upload <sandbox_id> <local> <remote>
+-- "delete sandbox file"              --> sandbox.py rm <sandbox_id> <path>
```

## Scripts

All scripts: `uv run --project ~/cc-plugins/cc-python python3 <script>`.
Working directory: this skill's `scripts/` folder.

### start.py -- Start a run

```bash
python3 start.py -p "user question"
# -> {thread_id, agent_run_id}
```

Print both IDs immediately.
User needs them for status checks and downloads.

### status.py -- Check or wait for status

```bash
python3 status.py <agent_run_id>          # one-shot check
python3 status.py <agent_run_id> --wait   # poll until terminal
```

Terminal statuses: `completed`, `failed`, `stopped`.

### sandbox.py -- Sandbox file operations

```bash
python3 sandbox.py ls <sandbox_id> /workspace
python3 sandbox.py cat <sandbox_id> /workspace/report.md
python3 sandbox.py download <thread_id> -o ~/scratch/sciencepal/<run_id>/
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
- NEVER assume sandbox is alive -- it auto-stops after 10min idle. Call `ensure-active` first if the run finished a while ago.
- NEVER download from a `failed` or `stopped` run -- sandbox may have incomplete/corrupt state.
- NEVER put downloaded files inside a project repo -- use `~/scratch/sciencepal/<run_id>/` or the project's data directory.
- NEVER poll status faster than every 10 seconds -- respect rate limits.
- NEVER expose or log the `SCIENCEPAL_ACCESS_TOKEN` value.

## Error Handling

| Error                     | Cause                                   | Fix                                     |
| ------------------------- | --------------------------------------- | --------------------------------------- |
| 401 Unauthorized          | Token expired or invalid                | Refresh token at sciencepal.ai          |
| 404 on `/agent-run/{id}`  | Invalid run ID                          | Check ID from start.py output           |
| 404 on sandbox file read  | File doesn't exist or sandbox destroyed | Try `sandbox.py ls` first to verify     |
| 422 on `/agent/initiate`  | Sent JSON instead of form-data          | Scripts handle this correctly           |
| 500 on sandbox operations | Sandbox crashed or being archived       | Call `ensure-active`, retry             |
| Timeout on `--wait`       | Task taking too long                    | Check status manually, increase timeout |

## Rules

- Print `thread_id` and `agent_run_id` immediately after starting.
- Output files go to `~/scratch/sciencepal/<run_id>/` or project data dir, not inside any project repo.
- Agent task results are in `/workspace` inside the sandbox.
- Tool/model files live in `/app` -- these are read-only base image contents, not task outputs.
