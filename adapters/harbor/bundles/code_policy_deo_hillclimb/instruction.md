# GameBench code policy hillclimb (Harbor workspace)

Your **cwd is this workspace root**. Read `AGENTS.md` for the task id and
candidate directory — those paths are authoritative for this lane.

## Objective

Improve the code policy so the hillclimb verifier passes. The verifier requires
the best **non-baseline** candidate to beat baseline by at least **+0.01**
(`pass-delta`). A smaller lift is progress but is not a pass — keep iterating.

## Do this

1. Study the baseline policy path listed in `AGENTS.md`.
2. Add new candidate(s) only under the candidate dir from `AGENTS.md`
   (for example `candidates/<subdir>/<candidate_id>/heuristic_policy.py`).
   Never write candidates for a different game family than the one in `AGENTS.md`.
3. Do not modify or delete existing candidate directories; only add new ones.
4. Run **sequentially**:

```bash
python3 workspace/run_gamebench_hillclimb_task.py run --output-root . --candidate-root candidates
python3 workspace/run_gamebench_hillclimb_task.py score --output-root .
```

5. If the score command fails because uplift is below +0.01, create another
   candidate and re-run. Do not stop after a sub-threshold improvement.
6. Do not edit files under `gamebench/tasks/`.

Execution budget: use no more than 12 read-only inspection commands before
creating the first candidate and running both verifier commands. Do not reread
the same source file unless a verifier result identifies a specific need.
