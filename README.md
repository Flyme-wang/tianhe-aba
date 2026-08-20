# tianhe-aba

> Abaqus 2024 在天河超算（SLURM）上的作业提交与管理 **Agent Skill**。

在 `DeepSeek Harness`、`Qoder`、`Cursor` 等支持 Skill 的 AI 代理中可直接使用：当用户要求
**在天河超算提交/运行 Abaqus 作业、监控作业、检查许可证、编译 Fortran 用户子程序（UMAT）**时，
代理会自动加载本 Skill，按已验证的流程操作，无需重新探索集群环境。

## 目录

- [仓库结构](#仓库结构)
- [集群事实（Skill 已固化）](#集群事实skill-已固化)
- [快速使用](#快速使用)
- [Fortran 用户子程序（UMAT）](#fortran-用户子程序umat)
- [常见问题](#常见问题)
- [相关仓库](#相关仓库)

---

## 仓库结构

```
tianhe-aba/
├── SKILL.md                    # Skill 主文件（frontmatter 路由 + 集群事实 + 工作流 + 排错）
└── scripts/
    ├── abaqus2024              # 启动包装器（补齐缺失系统库）
    ├── abaqus_v6.env           # 环境文件模板（SLURM hostlist + 许可证）
    ├── run_abaqus2024.sh       # 生产提交脚本（com_u22, 32 核, interactive）
    ├── install_std_solver.sh   # Standard 求解器补装（按 media.db 哈希）
    ├── tiny_std.inp            # 验证用单元素模型
    ├── tiny_std_test.sh        # 验证用 SLURM 脚本
    └── fortran/                # Fortran 用户子程序支持
        ├── abaqus2024_fortran  # 带 ifort 的启动包装器（make 时加载 Intel oneAPI）
        ├── umat_test.f         # 线性弹性 UMAT 示例
        ├── umat_e2e.inp        # 调用 UMAT 的测试模型
        └── umat_slurm_test.sh  # UMAT 端到端测试（SLURM）
```

## 集群事实（Skill 已固化）

| 项目 | 值 |
|---|---|
| 登录 | `ssh tianhe` → `121.46.19.4:6666`，用户 `apm_zcshen_5` |
| 调度器 | SLURM（tianhexy-cn） |
| 可用分区 | **com_u22**（Ubuntu 22.04，64 核/节点，许可证可达） |
| 许可证 | FLEXnet `27000@12.8.3.194`（com_u22 可达；mars/deimos/e9/phobos 不通） |
| 安装根 | `~/HDD_POOL/SIMULIA/EstProducts/2024`（官方 Abaqus 2024） |
| 包装器 | `~/bin/abaqus2024` |
| 作业目录 | `~/abaqus/abaqus2024-try/`（输出就地保存） |

> ⚠️ 不可用分区：`com_c76`（CentOS 7，glibc 2.28 墙）、`com_u22_8458`（节点 DOWN/DRAIN）、
> AI 分区（hx/h100x/a100x/a800x/lava*，独立平台，需门户访问）。

## 快速使用

### 提交作业

```bash
# 上传 inp
scp model.inp tianhe:~/abaqus/abaqus2024-try/

# 提交（32 核, com_u22, 48h）
ssh tianhe "cd ~/abaqus/abaqus2024-try && sbatch run_abaqus2024.sh model.inp"

# 监控
ssh tianhe "squeue -u apm_zcshen_5; tail -30 ~/abaqus/abaqus2024-try/model.sta"
```

### 结果

所有输出（`.sta`/`.msg`/`.dat`/`.odb`）就地写入 inp 所在目录，直接 `scp` 取回即可。

## Fortran 用户子程序（UMAT）

1. **一次性补装缺失组件**（接口文件 + `libstandardU_static.a`），详见 `SKILL.md` 的
   *Fortran user subroutines* 章节（从集群 Abaqus 2020/2017 复制）。
2. **编译**（包装器自动加载 Intel oneAPI 2024.2 / ifort）：

   ```bash
   ~/bin/abaqus2024 make library=umat_test.f   # 产物 libstandardU.so
   ```

3. **提交**（必须走 SLURM，登录节点 interactive 会因 PMPI 初始化缺失报
   `libstandardU.so: failed to map segment`）：

   ```bash
   sbatch scripts/fortran/umat_slurm_test.sh
   ```

## 常见问题

| 症状 | 解决 |
|---|---|
| `Abaqus could not locate the standard executable` | 运行 `scripts/install_std_solver.sh` 补装 |
| 作业只剩空 `.log`/`.com` | 加 `interactive` 参数 |
| `lmgrd is not running` | 用 com_u22 分区 |
| `GLIBC_2.28 not found` | 用 com_u22（Ubuntu 22.04） |
| `aba_param.inc not found` | 补装 `SMAUsubs/PublicInterfaces/`（见 SKILL.md） |
| `libstandardU.so: failed to map segment` | 必须通过 SLURM 运行 UMAT 作业 |

## 相关仓库

- **完整安装教程**：[Flyme-wang/abaqus2024-tianhe-install](https://github.com/Flyme-wang/abaqus2024-tianhe-install)
  （介质解压、无头安装、缺失库、Standard 补装、Fortran 配置全流程）
- **Qoder Skill 库**：[Flyme-wang/qoder-skills](https://github.com/Flyme-wang/qoder-skills)
  （HF 压裂敏感性分析专用版 tianhe-aba）
- **CAE-Agent-Hub**：[Flyme-wang/CAE-Agent-Hub](https://github.com/Flyme-wang/CAE-Agent-Hub)
  （CAE 多软件 Skill/MCP 合集）

---

*License: MIT · 作者 Flyme-wang · 适用于天河超算 Abaqus 2024 作业管理*
