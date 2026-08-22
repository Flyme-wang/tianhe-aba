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
- 水平内聚层: z=4/21 的 H_Z4/H_Z21 用独立材料 `MAT_COHESIVE_HORIZONTAL_DIAG`（参数同 XZ）+ 独立截面 `elset=CELL_COHESIVE_H_Z4/Z21`；全部内聚截面共用 `*Section Controls, name=VISCO_COH3D8P_REF, viscosity=0.05`（弱化水平层只动该材料/截面，XZ 不误伤）
- 泄漏: `*Fluid Leakoff` `5.879e-10, 5.879e-10`；`*Gap Flow` 黏度 `0.001`
- 地层(M1~M5): E≈15 GPa, ν≈0.084, 渗透率 5.6e-7~7.6e-7 m/s（高渗），上覆低渗层 1.7e-9~7.7e-9
- 初始地应力: S11=-79 / S22=-65 / S33=-70 MPa，孔压 30 MPa，孔隙比 0.11
- 历史结论: 原参数下泄漏 98.2%（ALEAKVR 662.8 m³ vs 缝内 2.7 m³），裂缝 t≈180s 停止扩展、SDEG 冻结 0.15~0.99
- 注入点几何: `GREGION_INJECTION_COH_MID_NATIVE` 9 节点沿 x 一字排开 x=160~240（间距 10 m）、y=200.05、z=0；井筒 (200,200)

## INP part 归属与 section 行号地图（hweak_v4.inp）

| Part（起始行） | 内容 |
|---|---|
| RockMass_M4（行 14） | M4 段垂直缝 240 单元（elset generate 4801-5040）+ H_Z21 水平层 1640 单元 |
| RockMass_M5（行 30055） | M5 段垂直缝 108 单元 + H_Z4 水平层 2214 单元 |
| RockMass_Upper（行 50848） | UPPER 段垂直缝 576 单元 |

| 行号 | 定义 |
|---|---|
| 30048 | M4 段缝截面（elset=CELL_COHESIVE_XZ） |
| 30051 | H_Z21 截面（elset=CELL_COHESIVE_H_Z21） |
| 50838 | M5 段缝截面（elset=CELL_COHESIVE_XZ） |
| 50844 | H_Z4 截面（elset=CELL_COHESIVE_H_Z4） |
| 169994 | UPPER 段截面（elset=CELL_COHESIVE_XZ_ACTIVE） |
| 179348 | *Section Controls VISCO_COH_H_WEAK viscosity |
| 179362-179370 | MAT_COHESIVE_HORIZONTAL_WEAK 材料块 |
| 179843 | *Soils 行（utol/stabilize/allsdtol） |
| 179867-179868 | *Cflow 注入行 |

**行号修改铁律**：行 30048 与 50838 文本完全相同（`elset=CELL_COHESIVE_XZ, material=MAT_COHESIVE_XZ`），sed 全局替换必误伤 → 用 Python 按行号精确改（splitlines + assert 校验行内容 + 按 index 替换）；UPPER 段用 CELL_COHESIVE_XZ_ACTIVE 独立 elset，天然不误伤。

## hweak_v4 成功数值配置（模式 B 基准，C 系列算例父本）

- *Soils: `utol=9e+08, stabilize=0.001, allsdtol=0.2, continue=NO`；时间行 `0.1, 3600., 1e-08, 2.5`
- *Section Controls: `VISCO_COH_H_WEAK, viscosity=0.2`（水平层专用；垂直缝仍 VISCO_COH3D8P_REF 0.05）
- 材料: H_WEAK QUADS `2e+06,2.8e+06,2.8e+06` / BK `5000.,15000.,15000.`；DIAG（原始强度）QUADS `1e7,1.4e7,1.4e7` / BK `50000.,150000.,150000.`
- 基准结果: H_Z4 350 损伤/206 破裂、H_Z21 6 损伤/0 破裂、垂直缝 M5 段破裂跨度 320 m

## 单参数敏感性 sed 模式（已验证）

| 参数 | sed 命令 | 修改点 |
|------|----------|--------|
| 地层渗透率 | `sed -i -e 's/5.58783e-07/1e-11/' -e 's/5.94076e-07/1e-11/' -e 's/5.59713e-07/1e-11/' -e 's/5.94983e-07/1e-11/' -e 's/7.55378e-07/1e-11/' -e 's/5.7e-07/1e-11/'` | M1~M5+OVERBURDEN 6 处 |
| 内聚面 Leakoff | `sed -i 's/5.879e-10/1e-12/g'` | 2 处（XZ+HORIZONTAL_DIAG） |
| 注入流量 | `sed -i 's/-0.0444444/-0.15/'` | 1 处 Cflow |
| 孔压容差 utol | `sed -i 's/utol=9e+08/utol=1e+06/'` | 1 处 *Soils |
| 水平层弱化（hweak 方案1） | 新建材料 `MAT_COHESIVE_HORIZONTAL_WEAK`（QUADS `2e+06, 2.8e+06, 2.8e+06`=×0.2、BK `5000.,15000.,15000.`=×0.1，弹性/密度/Leakoff/GapFlow 继承）+ `sed -i 's/elset=CELL_COHESIVE_H_Z4, material=MAT_COHESIVE_HORIZONTAL_DIAG/elset=CELL_COHESIVE_H_Z4, material=MAT_COHESIVE_HORIZONTAL_WEAK/'`（H_Z21 同模式） | 2 处截面引用 |

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

## SDEG 导出与几何分类统计（dump_sdeg_param.py + stat_sdeg_geom2.py）

- 导出: `nohup $HOME/bin/abaqus2024 python dump_sdeg_param.py <job>.odb sdeg_xyz_<name>.txt > dump_<name>.log 2>&1 &`（输出 4 列 `x y z SDEG`，双模型可并行 nohup）
- **几何 z 分类是唯一可靠分类**: `abs(z-3.95)<0.01` → H_Z4（2214 单元）；`abs(z-20.95)<0.01` → H_Z21（1640）；其余 → 垂直缝（924：M5 段 z<4、M4 段 4≤z<21、UPPER z≥21）。实例名+elset label 分类不可靠（曾得 HZ4=882/HZ21=642 与几何 2214/1640 矛盾），禁止使用
- 统计: `python3 stat_sdeg_geom2.py sdeg_xyz_a.txt sdeg_xyz_b.txt ...`（系统 python3 即可，纯文本处理）→ 输出各分类损伤/破裂数、M5 段破裂跨度 span、M4 段损伤
- 破裂判据: SDEG ≥ 0.99（QUADSCRT 被 cap 1.0 同理用 0.9999）
- 参数化教训: 统计脚本必须接受命令行文件参数，勿硬编码模型名循环（曾因硬编码 C4/C1 导致新文件被忽略）

## 天河无头三面 SDEG 截图（snap_sdeg_face.py 模式，2026-08 验证）

在 60GB ODB 上做出版级 SDEG 破裂云图，按 cohesive 面分别截图（H_Z4/H_Z21 水平层 + XZ 垂直缝），colorbar 固定 0.01~1.0（过滤未破裂区干扰）。

**运行方式**（环境变量传参，勿用 `--` 命令行参数——cae noGUI 下 sys.argv[1] 是 '-cae'）：

```bash
ODB=<job>.odb TAG=v4 OUTDIR=. OUTLOG=snap_v4_faces.log \
nohup $HOME/bin/abaqus2024 cae noGUI=snap_sdeg_face.py > snap_v4_faces_cae.log 2>&1 &
```

**核心链路**（每步均为踩坑验证）：

1. **必须 `abaqus cae noGUI`**（viewer noGUI 内核无 displayGroupOdbToolset 模块）
2. **先 `from caeModules import *` 再 `import displayGroupOdbToolset as dgo`**（直接 import 失败）
3. **print 不出 stdout** → 日志一律写文件（open + write + flush）
4. **显示组构造必须用 `LeafFromElementLabels(partInstanceName, labels)`**：
   - `LeafFromElementSets` 只查 assembly 级 elset（本模型 elsets 全在 instance 级 → 静默空 leaf → 3301 字节空白图）
   - `LeafFromOdbElementLabels` 在本版本不存在（AttributeError）
   - labels 从 ODB elset 读取并过滤类型 `if e.type.startswith('COH')`（UPPER 的 CELL_COH_CONT_* 混有非 cohesive 岩石单元，不过滤出灰色污染区）
5. **多 instance 合并用 `displayGroup.add(leaf=...)`**（非 addLeaf；DisplayGroup 无 isEmpty 方法，勿判空）
6. **replace 之后必须完整重做渲染序列**：`setPrimaryVariable(SDEG) → setFrame(step=int, frame=nf-1) → display.setValues(plotState=(CONTOURS_ON_DEF,))`，否则不出图
7. **colorbar**：`contourOptions.setValues(minAutoCompute=False, maxAutoCompute=False, minValue=0.01, maxValue=1.0, numIntervals=9, intervalType=UNIFORM, outsideLimitsMode=SPECTRUM)`
8. **图例 24pt**：`viewportAnnotationOptions.setValues(legendFont='-*-verdana-bold-r-normal-*-*-240-*-*-p-*-*-*')`（X11 字体格式；无 legendFontSize/legendFontBold 参数）
9. **分辨率**：`vp.setValues(width=420, height=315)`（printToFile 无 size 参数）
10. **正交视角**（PARALLEL 投影 + fitView）：水平层俯视 `cameraPosition=(200,200,800), cameraTarget=(200,200,3.95|20.95), cameraUpVector=(0,1,0)`；垂直缝侧视 `cameraPosition=(200,900,11), cameraTarget=(200,200,11), cameraUpVector=(0,0,1)`

**单元数校验**（日志确认 leaf 大小）：H_Z4=2214、H_Z21=1640、XZ=924（M5 段 108 + M4 段 240 + UPPER 段 576）。

**脚本**（本地 `scripts/snap_sdeg_face.py` 全量 + `scripts/run_snap_faces.sh` 批量）：

```python
# 关键骨架（完整版见 scripts/snap_sdeg_face.py）
from caeModules import *          # 必须最先
import displayGroupOdbToolset as dgo
odb = openOdb(os.environ['ODB'], readOnly=True)
def labels_leaf(inst_name, elsets):
    labs = set()
    for sn in elsets:
        if sn in odb.rootAssembly.instances[inst_name].elementSets:
            for e in odb.rootAssembly.instances[inst_name].elementSets[sn].elements:
                if e.type.startswith('COH'):
                    labs.add(e.label)
    return dgo.LeafFromElementLabels(inst_name, tuple(sorted(labs)))
# 每面: replace(leaves[0]) -> add(leaves[1:]) ->
#   setPrimaryVariable(SDEG, INTEGRATION_POINT) -> setFrame -> plotState ->
#   contourOptions -> view.setValues -> fitView -> printToFile
```

**批量模式**（run_snap_faces.sh，每模型一次会话截三面，约 8 分钟/模型）：

```bash
for pair in "hweak_v4:v4" "sens_c1_q2x:c1"; do
  odb="${pair%%:*}"; tag="${pair##*:}"
  ODB=..._${odb}.odb TAG=${tag} OUTDIR=. OUTLOG=snap_${tag}_faces.log \
    $HOME/bin/abaqus2024 cae noGUI=snap_sdeg_face.py >> snap_faces_batch_cae.log 2>&1
done
```

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

## hweak 敏感性系列 C1~C6（2026-08，水平/垂直破裂主控因素）

hweak_v4 成功后系统回答「水平层起裂主控因素」。所有算例基于 hweak_v4 只改一个物理参数（+必需数值稳定参数）：

| 算例 | 修改 | H_Z4 损伤/破裂 | H_Z21 损伤/破裂 | M5 段跨度 | 结论 |
|---|---|---|---|---|---|
| v4 基准 | — | 350/206 | 6/0 | 320m | 模式 B |
| C4 | 水平层恢复原强度（WEAK→DIAG） | 0/0 | 0/0 | **135m** | 强度=开关；且 H_Z4 破裂提供横向通道助垂直缝扩展（修正「泄压阻高」旧认识） |
| C1 | 流量×2（0.4→0.8 m³/s） | 332/182 | 6/0 | 300m | 流量无效：净压力受地应力+强度控制已饱和 |
| C5 | 水平层 BK×2（5000→10000） | **失败 t=172s** | — | — | 软化区延长→snap-through 失稳，孔压振荡 -5.58 GPa |
| C5r1 | BK×2 + vis 0.3 + stab 0.003 | 251/122 | 18/0 | 220m | BK 加倍抑制破裂（需更多能量） |
| C2 | H_Z21 QUADS×0.5（2→1 MPa） | 350/206 | **230/30 ✅** | 320m | **实现双水平层破裂（模式 C）** |
| C3 | M4 段缝 QUADS×0.5（10→5 MPa） | 待分析 | — | — | 缝高阻力测试 |
| C6 | 流量×2+BK×2+vis0.3+stab0.003 | 待分析 | — | — | 组合协同测试 |

**核心物理结论**：水平层起裂强度（QUADS）是开关型主控——H_Z21 从 2 MPa 降至 1 MPa 即被垂直缝诱发破裂；断裂能（BK）为次级因素且方向相反（加倍反而抑制破裂）；流量补充无效。

## 水平层弱化实施流程（hweak 模式，submit_hweak.sh 已验证）

目标：让 H_Z4/H_Z21 水平面破裂。基准模型水平层 SDEG=0 永不张开（需缝压 > S33 70MPa + 抗拉 7~14MPa ≈ 77~84MPa，当前缝压远低于此）。

1. **探测**（probe_inp_sets.sh）：`grep -n 'Elset.*H_Z4\|Elset.*H_Z21'` + `grep -n 'Material.*HORIZONTAL\|Material.*XZ'` + `grep -n 'Cohesive.*H_Z'` 确认水平层有独立 set/材料/截面
2. **插入新材料块**（sed 多行插入易错 → split+append）：`sed -n '1,179360p' in > p1` → `cat >> p1 << 'MATEOF'`（新 *Material 块：*Damage Initiation QUADS / *Damage Evolution BK / *Density / *Elastic TRACTION / *Fluid Leakoff / *Gap Flow）`MATEOF` → `sed -n '179361,$p' in > p2` → `cat p1 p2 > out; rm p1 p2`
3. **改截面引用**：`sed -i 's/elset=CELL_COHESIVE_H_Z4, material=MAT_COHESIVE_HORIZONTAL_DIAG/elset=CELL_COHESIVE_H_Z4, material=MAT_COHESIVE_HORIZONTAL_WEAK/'`（Z21 同模式）
4. **验证**：`grep -c MAT_COHESIVE_HORIZONTAL_WEAK` 应 =3（1 定义 + 2 引用）；`grep 'Cohesive.*XZ'` 确认垂直缝未动
5. **提交 + 观测**：弱化后失败点从基准 120s 推迟到 185s = 水平层开始响应；再套收敛修复矩阵

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

## 监控自动接力（monitor_*.sh 模式）

计算完成后自动提交下一批算例 / 自动后处理，nohup 后台：

```bash
nohup bash monitor_c3c6.sh > /dev/null 2>&1 &
```

脚本骨架：

```bash
for i in $(seq 1 240); do
    grep -q "COMPLETED SUCCESSFULLY" $STA 2>/dev/null && ...   # 成功
    grep -q "HAS NOT BEEN COMPLETED" $STA 2>/dev/null && ...   # 失败也释放槽位
    # 完成后: sbatch 下一批 / 启动 dump + stat，用 flag 文件防重复
    sleep 600
done
```

- flag 文件（touch flag_xxx_submitted）防重复提交；kill 监控进程不影响计算作业
- 自动 dump 后等文件大小不再增长（stat -c %s 两次对比）再跑统计，避免读到半截文件

## 多核提交（30 核 threads / 330 核跨节点 MPI）

- com_u22 分区: 28 节点 × 64 核 = 1792 核，512 GB/节点
- 30 核（常规）: `--nodes=1 --ntasks-per-node=30`，Abaqus `cpus=30 mp_mode=threads`
- 330 核: `--nodes=6 --ntasks-per-node=64 --ntasks=330`，Abaqus `cpus=330 mp_mode=mpi`（跨节点必须 mpi；env 文件 mp_host_list 由 SLURM_NODELIST 经 scontrol show hostname 展开，「Unknown keyword」警告无害）
- **squeue %C 列显示节点 CPU 槽位数（64），非实际核数**；确认实际核数看 slurm out 的 `cores:` 行
- 2026-08 经验: 本模型 330 核 MPI 可正常启动求解，但用户最终统一回退 30 核单节点（threads，数值行为一致且排队快）

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
| sed 多行插入材料块易出错 | 放弃 `Na\...` + $'\n' 拼接；改用 split+append：sed -n 按行号切成 p1/p2 → `cat >> p1 << 'EOF'` 插入新块 → `cat p1 p2` 合并 → rm 临时文件 |
| 泄漏导致裂缝不扩展 | 降低地层渗透率/Leakoff，或增大 Cflow（详见敏感性 sed 表） |
| 弱化水平层后 t≈185s 整层同时软化发散 | 负特征值 200+/步且对 min inc/stabilize 鲁棒 = snap-through。新建 `*Section Controls, name=..., viscosity=0.5`：`sed -i '179347a\*Section Controls, name=VISCO_COH_H_WEAK, viscosity=0.5'` 行号插入定义，再用 material 名唯一定位 H 截面替换 controls（H 用 MAT_COHESIVE_HORIZONTAL_*，XZ 用 MAT_COHESIVE_XZ，sed 模式互不误伤） |
| 登录节点无 abaqus 命令 | PATH 无 abaqus → 用 `$HOME/bin/abaqus2024 python` 调 ODB 分析，禁止裸 `abaqus python` |
| 后台分析疑似未启动 | `ps aux | grep 脚本名` 确认存活；nohup 日志第一行应为 `== open`，60GB ODB 打开需 3~8 分钟 |
| 提交时禁止 kill 其他任务 | 仅用户明确指定才终止 |
| 相同文本 section 多处出现（行 30048/50838） | sed 全局替换必误伤 → Python 按行号 splitlines+assert+index 替换，或利用 elset 名差异定位 |
| 实例+elset 分类 SDEG 统计与几何矛盾 | 用几何 z 坐标分类（3.95/20.95），禁止实例 label 分类 |
| Windows 上传脚本 CRLF 行尾 | 超算执行前 `sed -i "s/\r//" file.py` |
| BK 断裂能加倍致发散（t=172s，孔压振荡负值） | 软化区延长→snap-through 增强；vis 0.2→0.3 + stab 0.001→0.003；仍失败则 BK 降 ×1.5 |
| squeue %C 显示 64 核疑似超额 | 那是节点槽位数；实际核数看 slurm out 的 cores 行 |
| 330 核排队时间过长 | 6 节点大资源申请易 PD；本模型 30 核单节点已足够，回退 threads |

## GitHub 托管与双端同步

- 仓库: `https://github.com/Flyme-wang/tianhe-aba`（私有，独立仓库，含 SKILL.md + metadata.json + sync_instructions.md）
- 本地: `C:\Users\Dell\.qoder\skills\tianhe-aba`（git 仓库，分支 main）
- 推送: `cd C:\Users\Dell\.qoder\skills\tianhe-aba ; git add . ; git commit -m "..." ; git push origin main`（PowerShell 用 `;` 连接，禁止 `&&`）
- 每日自动同步: schedule MCP 定时任务（daily 00:00 Asia/Shanghai, task id 6760f4f0-ff26-43e6-9b8e-a796e867ea6e）：pull → add → 有变更则 commit "auto sync $(Get-Date)" + push
- 每次 SKILL.md 更新后主动 commit+push，勿等午夜定时任务（本地 harness 与远端立即一致）；并在文末「更新日志」表追加一行（日期/提交/内容解释）
- gh repo create 报"仓库已存在" → 直接 `git init` + `git remote add origin <url>` + `git push -u origin main`，无需删除重建
- metadata.json 字段: `"repo": "Flyme-wang/tianhe-aba"`, `"path": "SKILL.md"`, `"source_url": "https://github.com/Flyme-wang/tianhe-aba"`

## 更新日志（每次推送后追加一条）

> 规范：每次 SKILL.md 更新并推送 GitHub 后，在本表追加一行（日期 / commit 前 7 位 / 本次新增内容的解释），保证本地 harness 与远端使用者都能追溯变更。

| 日期 | 提交 | 更新内容与解释 |
|---|---|---|
| 2026-08-20 | 2ca9e61 | **全面补录本窗口调试经验**：①参数模板补充水平层 INP 结构——H_Z4/H_Z21 用独立材料 MAT_COHESIVE_HORIZONTAL_DIAG（参数同 XZ），全部内聚截面共用 VISCO_COH3D8P_REF(viscosity=0.05)，弱化水平层只动该材料/截面不误伤 XZ；②敏感性 sed 表新增水平层弱化完整模式（新建 WEAK 材料 QUADS ×0.2/BK ×0.1 + 替换 2 处截面引用）；③新增「水平层弱化实施流程」五步章节（探测→split+append 插入→改截面→grep 验证→提交观测）；④陷阱表新增 sed 多行插入改用 split+append；⑤新增「GitHub 托管与双端同步」章节（仓库/推送命令/午夜定时任务/gh 已存在处理/metadata 字段） |
| 2026-08-20 | b0f770e | **hweak 系列调试经验**：①失败模式定位表新增 snap-through 诊断法——负特征值暴增（200+/步）且失败时刻对 min inc/stabilize 鲁棒 = 整层同时软化，非时间积分问题；②收敛修复矩阵新增 cohesive viscosity 参数（*Section Controls 0.05→0.5 仅弱化层截面，垂直缝保持 0.05）；③实验记录追加 hweak v1（弱化死 185s，22 负特征值/步）→v2（数值参数无效，负特征值暴涨 265/步）→v3（粘性正则化）三轮；④陷阱表新增弱化水平层 t≈185s 发散的修复操作（sed 行号插入 controls 定义 + material 名唯一定位截面） |
| 2026-08-21 | f87d4a4 | **敏感性系列 C1~C6 与后处理体系**：①新增「INP part 归属与 section 行号地图」——RockMass_M4/M5/Upper 三 part 的缝段与水平层归属，30048/50838 相同文本行必须按行号 Python 精确修改；②新增「hweak_v4 成功数值配置」基准（vis0.2+stab0.001+allsdtol0.2）与注入点几何（9 点 x=160~240）；③新增「敏感性系列 C1~C6」结果表——C2（H_Z21 QUADS×0.5）实现双水平层破裂（230/30），物理结论：起裂强度=开关、BK 次级且反向、流量无效；④新增「SDEG 导出与几何分类统计」——dump_sdeg_param.py 4 列输出 + stat_sdeg_geom2.py 几何 z=3.95/20.95 分类（实例 label 分类不可靠）；⑤新增「监控自动接力」monitor 模式与「330 核跨节点 MPI」提交要点；⑥陷阱表补充 5 条（行号修改、几何分类、CRLF、BK×2 发散修复、核数确认） |
| 2026-08-22 | 736b2c1 | **天河无头三面 SDEG 截图体系**：①新增「天河无头三面 SDEG 截图」章节——cae noGUI + caeModules + LeafFromElementLabels 完整链路（含 10 条核心步骤：环境变量传参、文件日志、colorbar 0.01~1.0、24pt X11 legendFont、正交视角参数）；②关键 API 陷阱：LeafFromElementSets 只查 assembly 级 elset（instance 级静默空）、LeafFromOdbElementLabels 不存在、DisplayGroup 无 isEmpty/add 非 addLeaf、replace 后必须重做渲染序列、单元类型 COH 过滤防灰色污染；③附 scripts/snap_sdeg_face.py（三面截图）与 run_snap_faces.sh（批量）到 skill 仓库 |
