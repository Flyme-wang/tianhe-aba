# tianhe-aba Skill

在天河超算（SLURM）上运行 Abaqus 2024 全耦合孔隙流体-内聚单元（COH3D8P）水力压裂分析的完整工作流：INP 单参数批量生成、作业提交、状态监控、ODB 结果提取与本地分析。

## 适用场景

- 用户要求"在天河超算提交/运行 Abaqus 作业"或"检验 ODB 计算结果"
- 水力压裂、全内聚单元模型、Soils 固结分析（*Soils, consolidation）
- 多模型单参数敏感性对比（渗透率 / 内聚面 Leakoff / 注入流量 / utol 容差等）

## 连接与环境

- SSH Host: `tianhe`（`~/.ssh/config`：Hostname 121.46.19.4, Port 6666, User apm_zcshen_5, 密钥 tianhe_key, 登录节点 ln233）
- 作业目录: `/XYFS01/HOME/apm_zcshen/apm_zcshen_5/abaqus/abaqus2024-try`
- Abaqus: `$HOME/bin/abaqus2024`（2024 版）
- 许可证: `27000@12.8.3.194`（SLURM 脚本内自动写入 `abaqus_v6.env`）
- 编译库: `export LD_LIBRARY_PATH=$HOME/HDD_POOL/abaqus2024_libs:$LD_LIBRARY_PATH`
- 本地 PowerShell 铁律：**禁止内联 `python -c "..."`**（引号转义必然失败）→ 一律写 .py/.sh 脚本文件再执行；ssh 双引号内 sed 表达式用单引号包裹；**批量循环/变量展开（`${var}`、`$f`）一律写 .sh 脚本上传执行**，PowerShell 会抢先展开 `${}` 导致参数变空

## 批量提交脚本模式（submit_sensitivity.sh，已验证）

```bash
#!/bin/bash
cd /XYFS01/HOME/apm_zcshen/apm_zcshen_5/abaqus/abaqus2024-try
BASE=CodexTarget49_CAE_NATIVE_allcohesive_gc50x_maxinc2p5
for f in perm1e11 leak1e12 flow0p15 utol1e6; do
    J=${BASE}_${f}
    sbatch run_abaqus2024.sh ${J}.inp
done
sleep 5
squeue -u apm_zcshen_5
```

提交后立即核对 slurm 输出头两行 `Job:`/`input:` 是否为完整文件名（若显示 `.inp` 或空 = 参数传递失败，需改用脚本方式）。

## 2026-08 四模型单参数敏感性任务（jobid 7030598-7030601/7030903）

| jobid | 模型后缀 | 修改参数 | 状态 |
|-------|----------|----------|------|
| 7030598 | perm1e11 | M1~M5+OVERBURDEN 渗透率 → 1e-11 m/s | 运行 |
| 7030599 | leak1e12 | 内聚面 Fluid Leakoff → 1e-12 | 运行 |
| 7030600 | flow0p15 | Cflow 注入 → -0.15 m³/s | 运行 |
| 7030601 | utol1e6 | utol 9e8 → 1e6 Pa | **失败**：TOO MANY ATTEMPTS，增量连续截断不收敛 |
| 7030903 | utol1e7 | utol 9e8 → 1e7 Pa | 替代重提 |

均基于 maxinc2p5 基准（最大步长 2.5 s），`sbatch run_abaqus2024.sh` 32 核提交，分区 com_u22。

## 提交工作流（五步）

1. **生成/修改 INP**：基于已验证的基准 inp 复制 + `sed` 单参数修改（敏感性模型每模型只改一个参数，保持其他不变）
2. **校验**：`grep -n` 确认修改点数量与内容，并对比基准行确认其余未动
3. **提交**：`sbatch run_abaqus2024.sh <job>.inp`（32 核, partition=com_u22, 48h, 输出 slurm-<jobid>.out/.err）
4. **监控**：`squeue -u $USER`；`tail slurm-*.out`；`.sta` 文件看增量步进度；异常查 `.msg`/`.dat`
5. **提取**：上传 `tianhe_run_probe.sh` + 分析脚本 → `bash tianhe_run_probe.sh <script>.py <job>.odb` → scp 下载 JSON/文本结果

## 关键参数模板（CodexTarget49 全内聚压裂模型）

- 模型: 三维 400×400×150 m，M5(0-4m)/M4(4-21m)/UPPER(21-150m)；y=200.1 预置垂直裂缝面；z=4/21 水平内聚层；M5 段 INITIAL GAP 预置 85 m 起裂条带（14 单元）
- 步: `*Soils, consolidation, end=PERIOD, utol=9e+08, stabilize=0.0002, allsdtol=0.05`；时间行 `0.1, 3600., 1e-08, 2.5`（初始 0.1s, 总 3600s, 最小 1e-8, **最大 2.5s**）
- 注入: `*Cflow, amplitude=Inject_Smooth300` → `GREGION_INJECTION_COH_MID_NATIVE, , -0.0444444`（9 节点集合，SMOOTH STEP 300s 升载）
- 内聚材料: QUADS 损伤起始 `1e7, 1.4e7, 1.4e7` Pa；BK 断裂能 `50000,150000,150000` J/m²；TRACTION 弹性 `4e10, 1.66667e10`；Density 2100
- 泄漏: `*Fluid Leakoff` `5.879e-10, 5.879e-10`；`*Gap Flow` 黏度 `0.001`
- 地层(M1~M5): E≈15 GPa, ν≈0.084, 渗透率 5.6e-7~7.6e-7 m/s（高渗），上覆低渗层 1.7e-9~7.7e-9
- 初始地应力: S11=-79 / S22=-65 / S33=-70 MPa，孔压 30 MPa，孔隙比 0.11
- 历史结论: 原参数下泄漏 98.2%（ALEAKVR 662.8 m³ vs 缝内 2.7 m³），裂缝 t≈180s 停止扩展、SDEG 冻结 0.15~0.99

## 单参数敏感性 sed 模式（已验证）

| 参数 | sed 命令 | 修改点 |
|------|----------|--------|
| 地层渗透率 | `sed -i -e 's/5.58783e-07/1e-11/' -e 's/5.94076e-07/1e-11/' -e 's/5.59713e-07/1e-11/' -e 's/5.94983e-07/1e-11/' -e 's/7.55378e-07/1e-11/' -e 's/5.7e-07/1e-11/'` | M1~M5+OVERBURDEN 6 处 |
| 内聚面 Leakoff | `sed -i 's/5.879e-10/1e-12/g'` | 2 处（XZ+HORIZONTAL_DIAG） |
| 注入流量 | `sed -i 's/-0.0444444/-0.15/'` | 1 处 Cflow |
| 孔压容差 utol | `sed -i 's/utol=9e+08/utol=1e+06/'` | 1 处 *Soils |

## ODB 提取要点（tianhe_run_probe.sh 模式）

- bulkDataBlocks：COH3D8P 每单元 4 积分点 → `data[:,0].reshape(-1,4).max(axis=1)` 取单元最大，`elementLabels.reshape(-1,4)[:,0]` 取标签
- SDEG 多 instance 分块：按 M5→M4→UPPER 顺序对应，先打印每块 instance 名再处理
- QUADSCRT 被 Abaqus cap 在 1.0：判据用 `>= 0.9999` 而非 `> 1.0`
- 关键变量: SDEG/PFOPEN/QUADSCRT/GFVR/ALEAKVR*/LEAKVR*（泄漏核算用 ALEAKVR 累计量 + PFOPEN×单元面积求缝内体积）
- 帧时间不一致时对比用最近邻插值（`min(ts, key=abs(x-t))`）
- 探针输出写文件（避免 tail 截断）：脚本内 `P()` 双输出到 txt + stdout

## 后台 ODB 分析调用（正确姿势）

- **禁止裸 `abaqus python`**：登录节点 PATH 无 abaqus → 必须 `$HOME/bin/abaqus2024 python <script>.py <odb>`
- 60GB ODB 打开+构建质心映射需 3~8 分钟，必须 nohup 后台跑：
  `nohup $HOME/bin/abaqus2024 python analyze.py job.odb > analyze.log 2>&1 &`
- 先 `ps aux | grep analyze.py` 确认进程存活，再 `sleep 240; cat analyze.log` 取结果
- 多模型依次后台跑（每模型独立 log），输出 JSON 到 `fracture_analysis/` 目录

## 运行状态检测与失败诊断（check_job_status2.sh 模式）

一键脚本（每模型检查三处，全部一次完成）：

```bash
squeue -u apm_zcshen_5                                        # 1. 调度状态 R/PD/空
sta=..._${suf}.sta; tail -5 $sta                               # 2. 增量推进：TIME/步长/U 标志
msg=..._${suf}.msg; grep -cE '\*\*\*ERROR|TOO MANY ATTEMPTS'  # 3. 错误扫描
```

判读规则：
- `tail -5 $sta` 末行 TIME=3600 + `THE ANALYSIS HAS COMPLETED SUCCESSFULLY` → 成功
- 末行 `THE ANALYSIS HAS NOT BEEN COMPLETED` → 失败，配合 .msg 错误定位
- 增量步长长期 `1.000e-08` 且 U 连续 → 卡在瞬态，增量下限不足
- cutback 计数（grep -c 'U'）：成功模型通常 <10；失败模型 >20 且伴随错误

## 失败模式快速定位表（.msg 关键字 → 根因 → 修复）

| .msg 关键字 | 根因 | 修复 |
|---|---|---|
| `TOO MANY ATTEMPTS` | 容差过紧/瞬态过强，增量耗尽 | 放宽 utol/allsdtol，或 min inc 降 1e-12 |
| `TIME INCREMENT REQUIRED LESS THAN MINIMUM` | 增量下限不够小 | min inc 1e-8→1e-12 + initial 0.1→0.01 |
| `SOLUTION APPEARS TO BE DIVERGING` | 物理发散（如 leakoff 降+高渗地层振荡） | stabilize 0.0002→0.001；仍发散则参数组合物理失稳 |
| `TIME INTEGRATION ACCURACY TOLERANCE EXCEEDED` | 孔压变化率超限 | allsdtol 0.05→0.2；再失败则 utol 上限调松 |
| 大量 NEGATIVE EIGENVALUE（>100） | 单元完全损伤/刚度奇异 | 起裂瞬态伴随现象，配合上面修复 |
| 负特征值暴增（200+/步）+ 失败时刻对 min inc/stabilize 鲁棒 | 弱化层整层同时软化（snap-through），非时间积分问题 | cohesive 粘性正则化：新建 *Section Controls viscosity 0.05→0.5 只指向弱化层截面 |

## 收敛性修复参数矩阵（2026-08 实证）

| 参数 | 基准值 | 修复值 | 作用 |
|---|---|---|---|
| min increment | 1e-8 | **1e-12** | 起裂瞬态硬下限，四数量级余量 |
| initial increment | 0.1 | 0.01 | 平滑进入瞬态 |
| stabilize | 0.0002 | 0.001 | 阻尼抑制发散（单独不足，须配 min inc） |
| allsdtol | 0.05 | 0.2 | 放宽孔压变化率容差 |
| utol | 9e8 | 5e7~1e8 | 收紧容差下限（<5e7 起裂瞬态必挂） |
| cohesive viscosity（*Section Controls） | 0.05 | 0.5（仅弱化层截面） | 弱化层整层软化时渐进损伤；垂直缝 controls 保持 0.05 不污染其行为 |

**修复原则**：敏感性变量（Leakoff/utol/渗透率/流量）保持不变，仅加数值稳定参数，不污染对比结论；每轮只试 1-2 个组合，用 .sta 推进距离判断效果（v1 死 103s → v3 死 120s = 进步）。

## 2026-08 失败模型修复实验记录

| 版本 | 参数改动 | 结果 |
|---|---|---|
| leak1e12 v1 | 原始 | 死 113s：DIVERGING+需<1e-8 增量 |
| leak1e12 v2 | +stabilize=0.001 | 仍死 113s（stabilize 单独不足） |
| leak1e12 v3 | +stabilize 0.001+min 1e-12 | 死 114s：23 次 DIVERGING，物理发散 |
| utol1e7 v1 | utol=1e7 | 死 103s：ACCURACY TOLERANCE EXCEEDED |
| utol5e7 v3 | +stabilize 0.001 | 仍死 103s |
| utol1e8 v4 | +allsdtol 0.2+min 1e-12+stab 0.001 | 死 120s：仍超容差，utol<5e7 物理不可行 |
| hweak v1 | 水平层 QUADS ×0.2/BK ×0.1（促水平面破裂） | 死 185s：22 负特征值/步，水平层起裂即发散 |
| hweak v2 | +min 1e-12+stab 0.001+allsdtol 0.2 | 仍死 185s：负特征值暴涨 265/步，纯数值参数无效 |
| hweak v3 | +水平层 *Section Controls viscosity 0.05→0.5 | 验证粘性正则化能否渐进化整层软化（垂直缝 controls 不动） |

结论：**起裂瞬态（t≈100~120s）是数值墙**——低 Leakoff 与高渗地层组合产生物理振荡发散；utol 收紧存在 ~5e7 Pa 物理下限。遇此情况向用户提供：接受为敏感性边界 / 延长平滑升载（Smooth300→600）/ 继续调数值参数 三选项。

**hweak 系列新经验（水平层弱化）**：基准模型水平层 SDEG=0 永不张开；QUADS ×0.2 弱化后 t≈185s 水平层开始破裂（物理机制：垂直缝流体压力传至水平层→有效垂向应力转拉→低强度整层同时起裂）但模型立即发散。诊断要点：**两组不同数值设置死在完全相同时刻 + 负特征值数量暴涨（22→265/步）= 整层同时软化 snap-through，不是时间积分问题**，min inc/stabilize 均无效；修复方向是粘性正则化让损伤渐进发生。

## cohesive 破裂检查（tianhe_check_hplanes.py 模式）

检查成功模型的裂缝破裂情况（尤其两个水平面是否破裂）：

1. **几何分类**（COH3D8P 质心 + z-range）：`zrange<0.6 且 zmean≈4` → H_Z4；`zrange<0.6 且 zmean≈21` → H_Z21；其余薄层 → H_other；`zrange≥0.6` → V_XZ（垂直缝）
2. **破裂判据**（每单元取 4 积分点最大值）：`SDEG>0.99` = 完全破裂；`SDEG>0.1` = 损伤；`QUADSCRT≥0.9999` = 起裂（被 cap 在 1.0）；`PFOPEN>1e-9` = 张开
3. **破裂范围**：对 damaged/full 单元统计 x 范围（dx_dam/dx_full），判断是贯穿缝还是局部裂；同时输出 y/z 范围确认面归属
4. **采样帧**：`[120, 360, 1200, 3600]` 起裂期密、后期疏；帧定位用最近邻物理时间（秒）
5. **输出**：JSON 到 `fracture_analysis/`，每帧含各分类 n/n_full/n_dam/n_init/dx_dam/dx_full/SDEGmax

判读要点：
- 水平面 n_full=0 但 n_dam>0 → 面有损伤未贯穿（冻结 SDEG 0.15~0.99 属该模型历史特征）
- 垂直缝 V_XZ 的 dx_full 才是裂缝真实半长（注入点 y=200.1 两侧对称）
- 对比 perm1e11 vs flow0p15 的同帧 dx_full 即可量化参数敏感性

## 常见陷阱

| 问题 | 解决 |
|------|------|
| PowerShell 双引号内 `${var}` 被本地抢先展开为空 | 循环/批量命令一律写 .sh 脚本上传执行 |
| 提交后 `Job: .inp` 空参数 | 参数传递失败（同上），脚本方式重提 |
| PowerShell 内联 python 转义失败 | 写 .py 脚本文件执行，勿用 `python -c` |
| 输出被 tail 截断 | 脚本写文件 + P() 双输出 |
| 无损伤时 zmin/zmax 为 None | `f'{v or 0:.1f}'` |
| 作业段错误崩溃（SOIL） | 查 .msg；若裂缝已停止则结果仍可用，无需重跑 |
| utol 收紧过度致 TOO MANY ATTEMPTS | utol=1e6 时 Injection 增量连续截断失败；收敛下限约 1e7（孔压 30 MPa 的 33%），再紧需同步减小初始增量步 |
| 起裂瞬态不收敛（t≈100~120s） | 全部失败模型都卡在裂缝起裂窗口：leakoff 降低→发散+需 <1e-8 增量（300 负特征值）；utol 收紧→TIME INTEGRATION ACCURACY TOLERANCE EXCEEDED。修复：leak1e12 加 stabilize=0.001；utol1e7 放宽 allsdtol=0.05→0.2，均保持敏感性变量不变 |
| 起裂瞬态硬瓶颈是 min increment=1e-8 | stabilize=0.001 单独不足以过 t≈103~113s（leak1e12_v2/utol5e7_v3 仍死于此，增量耗尽到 1e-8）。必须同时放开最小增量 1e-8→1e-12 + 初始增量 0.1→0.01，给瞬态足够空间后自动恢复满步长 |
| sed 锚点 ^...$ 匹配失败 | INP 可能 CRLF 行尾，`^0.1, 3600., 1e-08, 2.5,$` 不匹配；改用无锚点 `s/0.1, 3600., 1e-08, 2.5,/0.01, 3600., 1e-12, 2.5,/` 并 grep 验证 |
| 泄漏导致裂缝不扩展 | 降低地层渗透率/Leakoff，或增大 Cflow（详见敏感性 sed 表） |
| 弱化水平层后 t≈185s 整层同时软化发散 | 负特征值 200+/步且对 min inc/stabilize 鲁棒 = snap-through。新建 `*Section Controls, name=..., viscosity=0.5`：`sed -i '179347a\*Section Controls, name=VISCO_COH_H_WEAK, viscosity=0.5'` 行号插入定义，再用 material 名唯一定位 H 截面替换 controls（H 用 MAT_COHESIVE_HORIZONTAL_*，XZ 用 MAT_COHESIVE_XZ，sed 模式互不误伤） |
| 登录节点无 abaqus 命令 | PATH 无 abaqus → 用 `$HOME/bin/abaqus2024 python` 调 ODB 分析，禁止裸 `abaqus python` |
| 后台分析疑似未启动 | `ps aux | grep 脚本名` 确认存活；nohup 日志第一行应为 `== open`，60GB ODB 打开需 3~8 分钟 |
| 提交时禁止 kill 其他任务 | 仅用户明确指定才终止 |
