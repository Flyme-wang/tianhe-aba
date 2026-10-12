---
name: tianhe-aba
description: Submit and monitor Abaqus 2024 jobs on the Tianhe (天河) HPC cluster via SLURM. Use when the user asks to run/submit/execute an Abaqus .inp job on the cluster, monitor a running Abaqus job, check license availability on the cluster, or upload/download model files to the Tianhe login node. Covers the com_u22 partition, the cluster FLEXnet license (27000@12.8.3.194), the abaqus2024 launcher wrapper, and the SLURM submission script that writes outputs in the inp folder.
---

# Tianhe Abaqus 2024 Job Submission (tianhe-aba)

Submit Abaqus 2024 `.inp` jobs to the Tianhe supercomputer and monitor them through completion. This skill knows the exact cluster layout, the legal license route, and the proven working scripts.

## Cluster facts (do not rediscover)

- **Login**: `ssh tianhe` (alias in local `~/.ssh/config`) → `121.46.19.4:6666`, user `apm_zcshen_5`, key `~/.ssh/tianhe_key`.
- **Scheduler**: SLURM (tianhexy-cn).
- **Working partition**: `com_u22` (Ubuntu 22.04, 64 cores/node, ~28 idle nodes). License `27000@12.8.3.194` IS reachable from com_u22.
- **Unusable partitions**: `com_c76` (CentOS 7, glibc 2.28 wall blocks Abaqus 2024), `com_u22_8458` (nodes DOWN/DRAIN), mars/deimos/e9/phobos (FLEXnet protocol unreachable).
- **Install root**: `~/HDD_POOL/SIMULIA/EstProducts/2024` (official Abaqus 2024).
- **Launcher wrapper**: `~/bin/abaqus2024` (sets `LD_LIBRARY_PATH=~/HDD_POOL/abaqus2024_libs`, `LIBGL_ALWAYS_INDIRECT=1`, execs the real `abaqus`). **Always submit through this wrapper** — it is the Abaqus 2024 install, not the system default Abaqus 2017.
- **Env file**: `~/abaqus_v6.env` (pure ASCII; builds `mp_host_list` from `SLURM_NODELIST`; license `abaquslm_license_file = "27000@12.8.3.194"`).
- **SSH flakiness is routine** ("banner exchange ... timed out"). Retry a few times; prefer uploading script files over long inline commands.

### 🔴 PUT JOBS IN `~/HDD_POOL/`, NEVER IN `~/abaqus/`

Measured 2026-10-12: the home-directory filesystem `/XYFS01` has a **user quota that is
essentially exhausted**.

| Path | Filesystem | Measured behaviour |
|---|---|---|
| `~/abaqus/` | `/XYFS01` | ❌ **writes truncate at ~8.4 MB** (`dd` of 50 MB produced only 8,368,128 B) |
| `~/HDD_POOL/` | `/XYFS02` (11 PB, 30 % used) | ✅ 50 MB writes complete |

Consequence: `scp` to `~/abaqus/...` fails with `write remote "...": Failure` after copying
only part of the file (a 19.6 MB inp transferred just 2.1 MB). **Always verify the remote
byte count and md5 after uploading**, and put the job under `~/HDD_POOL/<JOBNAME>/`.

```bash
ssh tianhe "mkdir -p ~/HDD_POOL/$JOB"
scp model.inp tianhe:~/HDD_POOL/$JOB/
ssh tianhe "stat -c %s ~/HDD_POOL/$JOB/model.inp; md5sum ~/HDD_POOL/$JOB/model.inp"
```

### Script files must have LF endings

PowerShell writes CRLF by default, which makes the remote bash fail with
`$'echo\r': command not found` and silently corrupts multi-line commands and SLURM scripts.

```powershell
[IO.File]::WriteAllText($path, ($sh -replace "`r`n", "`n"))   # then check CR count == 0
```

## Workflow: submit a job

### Step 1 — Ensure the inp is on the login node

Upload into **`~/HDD_POOL/<JOBNAME>/`** (never `~/abaqus/` — the home quota truncates writes):

```bash
ssh tianhe "mkdir -p ~/HDD_POOL/abaqus2024-try"
scp model.inp tianhe:~/HDD_POOL/abaqus2024-try/
ssh tianhe "stat -c %s ~/HDD_POOL/abaqus2024-try/model.inp"   # must match the local size
```

### Step 2 — Submit via SLURM

Run the production script `run_abaqus2024.sh` (it `cd`s into the inp folder, writes a local `./abaqus_v6.env` with the cluster license, and runs with `interactive` so the solver stays in the foreground):

```bash
ssh tianhe "cd ~/HDD_POOL/abaqus2024-try && sbatch run_abaqus2024.sh model.inp"
```

The script lives at `~/HDD_POOL/abaqus2024-try/run_abaqus2024.sh` and is also bundled in `scripts/`. Key settings: `--partition=com_u22`, `--ntasks-per-node=32`, `--time=48:00:00`, outputs `slurm-%j.out`/`slurm-%j.err` in the job folder.

**Choose the core count** via `--ntasks-per-node=N` together with `NCORES=${SLURM_NTASKS:-32}`
and `cpus=$NCORES`. `com_u22` nodes have 64 cores, so any N ≤ 64 fits on one node. The job
submits through `$HOME/bin/abaqus2024` (Abaqus 2024) — confirm `Abaqus 2024` appears in
`slurm-<jobid>.out` and that the license is checked out from `12.8.3.194`.

### Step 3 — Monitor

```bash
ssh tianhe "squeue -j <JOBID>; tail -30 ~/HDD_POOL/abaqus2024-try/<jobname>.sta"
```

The `.sta` file shows increment progress. `.msg` shows solver messages; `.dat` the printed output. All outputs are written **in the inp folder** (`~/HDD_POOL/abaqus2024-try/`).

### Step 4 — Collect results

```bash
scp -r tianhe:~/HDD_POOL/abaqus2024-try/<jobname>.odb .
```

## The production submission script

`scripts/run_abaqus2024.sh` (same content as on the cluster):

```bash
#!/bin/bash
# ============================================================
#  Abaqus 2024 SLURM 提交脚本（模仿门户 2017 脚本模式）
#  用法: sbatch run_abaqus2024.sh [input.inp]
#  特点: 在 inp 目录运行、输出就地保存、32 核、自动生成 env
# ============================================================
#SBATCH --job-name=abaqus2024
#SBATCH --partition=com_u22
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=32
#SBATCH --time=48:00:00
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err

INPUT_FILE=${1:-$(ls *.inp 2>/dev/null | head -1)}
if [ -z "$INPUT_FILE" ]; then echo "No inp file"; exit 1; fi

export JOB_WORKING_DIR=$(dirname $INPUT_FILE)
export NCORES=${SLURM_NTASKS:-32}
export JOB_NAME=$(basename $INPUT_FILE .inp)
export ABAQUS_EXECUTABLE=$HOME/bin/abaqus2024

cd "$JOB_WORKING_DIR"
echo "Workdir: $(pwd)"
echo "Job: $JOB_NAME, cores: $NCORES, input: $(basename $INPUT_FILE)"
echo "Node: $(hostname), Nodelist: $SLURM_NODELIST"

# 生成环境文件（SLURM MPI hostlist + 许可证）——模仿 abqenv2017.py
cat > ./abaqus_v6.env <<'ENVEOF'
import os, subprocess
hostsCompressed = os.getenv('SLURM_NODELIST', 'NONE')
if hostsCompressed != 'NONE':
    try:
        hostsExpanded = subprocess.check_output(
            'scontrol show hostname ' + hostsCompressed, shell=True)
        hostsList = [h for h in hostsExpanded.decode().split() if h.strip()]
        cpusPerNode = 64
        mp_host_list = [[h, cpusPerNode] for h in hostsList]
    except Exception:
        pass
abaquslm_license_file = "27000@12.8.3.194"
ENVEOF

export LD_LIBRARY_PATH=$HOME/HDD_POOL/abaqus2024_libs:$LD_LIBRARY_PATH

echo "Start: $(date)"
$ABAQUS_EXECUTABLE input=$(basename $INPUT_FILE) job=$JOB_NAME \
    cpus=$NCORES mp_mode=threads scratch=/dev/shm interactive
echo "Abaqus exit: $?"
echo "End: $(date)"
```

## Fortran user subroutines (UMAT/VUMAT)

The 2024 install **lacks the user-subroutine components**; they must be restored once. Reference: cluster Abaqus 2017 uses `ifort`.

### Restore missing components (one-time)

```bash
ABQ=$HOME/HDD_POOL/SIMULIA/EstProducts/2024
# 1) PublicInterfaces (26 files) — note: at install ROOT, sibling of linux_a64
mkdir -p $ABQ/SMAUsubs/PublicInterfaces
cp /APP/u22/x86_com/abaqus/Abaqus2020_HF6/SMAUsubs/PublicInterfaces/* $ABQ/SMAUsubs/PublicInterfaces/
# 2) site parameter inc files (aba_param_dp/sp, vaba_param*, etc.)
SRC=/APP/u22/x86_com/abaqus/Abaqus17/V6R2017x/linux_a64/SMA/site
for f in aba_param_dp.inc aba_param_sp.inc vaba_param_dp.inc vaba_param_sp.inc \
         aba_tcs_param.inc aba_evs_param.inc aba_globalvar_dp.inc aba_globalvar_sp.inc \
         SMACfdUserSubroutines.h; do
  [ -f "$SRC/$f" ] && [ ! -f "$ABQ/linux_a64/SMA/site/$f" ] && cp "$SRC/$f" "$ABQ/linux_a64/SMA/site/"
done
# 3) standard user subroutine static library
mkdir -p $ABQ/linux_a64/code/lib
cp /APP/u22/x86_com/abaqus/Abaqus2020_HF6/linux_a64/code/lib/libstandardU_static.a $ABQ/linux_a64/code/lib/
```

### Compile a user subroutine and run a job

```bash
# wrapper `scripts/fortran/abaqus2024_fortran` (deploy as ~/bin/abaqus2024) loads
# Intel oneAPI 2024.2 (ifort) ONLY for `make`/`python`; normal runs stay clean.
# 1) compile (produces libstandardU.so in cwd)
~/bin/abaqus2024 make library=umat_test.f
# 2) submit via SLURM — MUST go through sbatch, not login-node interactive
sbatch scripts/fortran/umat_slurm_test.sh   # or add user=your.f to run_abaqus2024.sh
```

> ⚠️ **Always run user-subroutine jobs through SLURM.** On the login node,
> interactive runs fail with `libstandardU.so: failed to map segment from shared
> object` because `libmpiCC.so`'s `hpmp_bor` symbol is only provided after full
> Platform MPI (PMPI) initialization, which happens inside SLURM jobs.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Abaqus could not locate the standard executable` | Standard solver was not installed by the installer | Reinstall from media: see `scripts/install_std_solver.sh` (media.db hash → CAFS zip → verify sha256) |
| Job finishes leaving only empty `.log`/`.com` | Missing `interactive` argument | Always use `interactive` so the solver runs in the foreground |
| `lmgrd is not running` / no checkout | Partition cannot reach FLEXnet | Use `com_u22`; only that partition has license access |
| `GLIBC_2.28 not found` | CentOS 7 (com_c76) | Use `com_u22` (Ubuntu 22.04) |
| `Unknown keyword (hostsCompressed)` warnings | env parsed by Abaqus; harmless | Ignore |
| `Include file aba_param.inc ... not found` | PublicInterfaces not installed | Restore from 2020 (see Fortran section) |
| `Abaqus user subroutine library could not be found` | `libstandardU_static.a` missing | Copy from 2020 `linux_a64/code/lib/` |
| `libstandardU.so: failed to map segment` | interactive run, no PMPI init | Run through SLURM only |
| SSH banner exchange timeout | Routine cluster flakiness | Retry a few times |
| `scp: write remote "...": Failure`, file truncated (e.g. 19.6 MB → 2.1 MB) | Home filesystem `/XYFS01` user quota exhausted | **Move the job to `~/HDD_POOL/`** (`/XYFS02`, 11 PB). See the 🔴 section above |
| `dd` / write stops at ~8.4 MB | Same quota | Same fix |
| `$'echo\r': command not found`, `head: invalid trailing option` | CRLF line endings in a script written by PowerShell | Rewrite with LF: `[IO.File]::WriteAllText($p, ($s -replace "`r`n","`n"))` |
| Job runs but is the wrong version (2017 not 2024) | Submitted via bare `abaqus` | Always use `$HOME/bin/abaqus2024` |

## Quick validation

After any change to the install (e.g. reinstalling solver files), run the tiny single-element Standard job before the real model:

```bash
ssh tianhe "mkdir -p ~/HDD_POOL/tiny_std_test"
scp scripts/tiny_std.inp scripts/tiny_std_test.sh tianhe:~/HDD_POOL/tiny_std_test/
ssh tianhe "cd ~/HDD_POOL/tiny_std_test && sbatch tiny_std_test.sh"
```

Expected: `THE ANALYSIS HAS COMPLETED SUCCESSFULLY` in `tiny_std.sta`.

## Abaqus MCP on the cluster — feasibility verdict

**Verdict: the Abaqus MCP (`Flyme-wang/CAE-Agent-Hub/MCP/Abaqus`) does not run on this cluster.** It requires a persistent CAE GUI session plus local Python dependencies, both unavailable in the headless, restricted login environment.

| MCP requirement | Cluster reality | Result |
|---|---|---|
| CAE GUI resident (bridge runs on GUI thread) | No Xvfb/Xvnc; no sudo to install | ❌ no headless start |
| Plugin unconditionally calls `getAFXApp().getAFXMainWindow()` | `cae noGUI` has no AFXApp main window | ❌ noGUI unusable |
| Depends on `mcp>=1.0` (pydantic/httpx/anyio) via pip | No pip on login node; external PyPI unreachable | ❌ deps cannot install |
| Local wheel relay | Local proxy dead, no direct internet | ❌ relay infeasible |

Use it on a local Windows machine with a local Abaqus install instead (`py -m venv .venv`, `pip install -e .` in `MCP/Abaqus/`, copy `abaqus_plugins/mcp_control` to `%USERPROFILE%\abaqus_plugins\`). On the cluster, use the SLURM workflow in this skill.

## Files in this skill

- `scripts/run_abaqus2024.sh` — production SLURM submission script (32 cores, com_u22).
- `scripts/tiny_std.inp` — minimal single-element Standard verification model.
- `scripts/tiny_std_test.sh` — SLURM verification job for the tiny model.
- `scripts/install_std_solver.sh` — reinstalls the missing `standard` solver executable from install media by media.db hash.
- `scripts/abaqus2024` — the launcher wrapper deployed as `~/bin/abaqus2024`.
- `scripts/abaqus_v6.env` — the environment file template (license + SLURM hostlist).
- `scripts/fortran/abaqus2024_fortran` — wrapper that loads ifort for `make` (deploy as `~/bin/abaqus2024` to enable UMAT).
- `scripts/fortran/umat_test.f` — working linear-elastic UMAT example.
- `scripts/fortran/umat_e2e.inp` — single-element model using the UMAT (`*User Material` + `*Depvar`).
- `scripts/fortran/umat_slurm_test.sh` — SLURM end-to-end UMAT test (com_u22).
