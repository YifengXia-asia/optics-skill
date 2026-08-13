---
name: vasp-optics-mc-v0-5
description: "Use when a user provides VASP POSCAR, POTCAR and KPOINTS and needs a system-adaptive independent-particle optical workflow: classify the actual structure, recommend reviewable parameters, wait for explicit confirmation, run DFT then LOPTICS, extract epsilon/n/k/alpha/reflectivity in energy and wavelength domains, and validate the results."
---

# VASP 体系自适应独立粒子光学工作流 v0.5

## 1. Overview

本技能把三个用户输入文件变成一套可检查的 VASP 独立粒子光学结果：

`POSCAR + POTCAR + KPOINTS → 检查/分类 → 参数建议 → 用户确认 → DFT → LOPTICS → vasprun.xml 解析 → 能量域和波长域 CSV/PNG → 只读验证`

材料名称不是分支条件。分类只使用输入文件中的晶格、元素、赝势信息和 K 点；`material`、`prefix` 只控制显示名和输出文件名，用户可以修改，不会因此改变物理模型。

这是 Linux/Unix 上的阶段一 demo，默认采用独立粒子、无 GW/BSE、无 SOC、无声子/离子介电响应的近似。自动建议是起始值，不是收敛证明；定量发表前仍要做 ENCUT、K 点、NBANDS、CSHIFT/NEDOS 收敛测试。

## 2. When to Use

当用户已有相同晶胞的 `POSCAR`、`POTCAR`、`KPOINTS`，想得到 `epsilon1/epsilon2/n/k/alpha/reflectivity` 及能量、波长曲线时使用。

在以下情况不要直接套用本流程，先说明物理边界并要求单独方案：结构弛豫、金属费米面光学、强磁性、SOC、GW/BSE、声子/离子介电响应、局域场效应，以及分子/二维体系的真空归一化或厚度定义。分类器会给出风险提示，但不会把风险体系伪装成普通三维体相。

明确拒绝的请求示例：

- “只有 CONTCAR，没有 POTCAR，先随便找一个赝势继续”：停止，要求用户提供与元素、顺序一致的 POTCAR。
- “不确认建议就直接覆盖已有 stage1_demo”：停止，要求新建 `output_dir` 或显式确认人工操作。
- “用本流程替代 GW/BSE 或实验厚度吸收率”：停止并说明本技能只给独立粒子介电函数、吸收系数和法向入射反射率。

## 3. Prerequisites

### 3.1 用户输入

在同一个 `run.input_dir` 中必须存在以下非空普通文件；脚本只读它们并复制到新运行目录，不会修改原件。

| 文件 | 必须内容 | 关键检查 |
|---|---|---|
| `POSCAR` | VASP 4/5 格式；晶格矢量、元素（VASP 4 可由 POTCAR 补充）、原子数 | 元素数与计数可解析；晶格长度用于三维/二维/孤立体系候选分类 |
| `POTCAR` | 按 POSCAR 元素顺序拼接的真实赝势 | 每个块读取 `TITEL`、`ENMAX`、`ZVAL`；顺序和块数必须一致 |
| `KPOINTS` | 显式 Gamma 或 Monkhorst-Pack 网格与偏移 | 网格、模式和偏移可解析；显式配置时必须与实际文件一致 |

本技能不下载、编译或猜测 POTCAR。没有 POTCAR 不能认为 VASP 结果可信。

### 3.2 软件环境

运行 VASP 阶段需要 Linux/Unix shell、可执行的 `vasp_std`、`mpirun`、`timeout`，以及可加载的 oneAPI/MKL（若集群要求）。后处理至少需要 Python 3.10+、PyYAML、NumPy、pandas、matplotlib；`xml.etree.ElementTree` 为 Python 标准库，lxml 可作为用户环境中的兼容依赖但不是本版本解析器的硬性依赖。脚本默认以 `python` 调用，若服务器只有环境内解释器，应写绝对路径或先激活环境。

Windows 不直接运行这些 VASP shell 步骤；请使用 WSL 或远程 Linux 服务器。只做配置检查/后处理时，Windows Python 也可运行相应脚本，但 `run.py` 仍需要 Bash、MPI 和 VASP。

## 4. Configuration and Parameter Policy

复制 `config.yaml.example` 为 `config.yaml`，先保留 `auto`，再执行：

```bash
python scripts/config_loader.py --config config.yaml --inspect
```

只读审阅输出中的 `STRUCTURE_CLASS`、`ELECTRONIC_CHARACTER`、`POTCAR_ELEMENTS`、`MAX_ENMAX`、`KPOINTS_ACTUAL` 和 `RECOMMENDED`。审阅后才把 `run.confirm_recommendations` 改为 `true`。在确认前，`check` 和 `prepare.py` 都必须失败，不能创建输出目录。

参数决策不是材料名称匹配：

- `ENCUT`：取实际 POTCAR 最大 `ENMAX`，向上取整到 10 eV；显式值低于最大 `ENMAX` 时拒绝准备。
- `KPOINTS`：按晶格长度估算起始网格；疑似真空方向设为 1。不会自动重写用户的 KPOINTS；显式 `parameters.kpoints` 或偏移不一致就失败。
- `NBANDS`：用 `ZVAL × 原子数` 估算占据带，再加空带余量。目标能量越高，空带越要增加；必须用更大 NBANDS 做收敛比较。
- `ISMEAR/SIGMA`：用户在 `system_hint` 指明 `insulator`、`semiconductor` 或 `metal` 时给起始值；`auto` 且未知时报告 `unknown-needs-dft-check`，不能声称已有带隙。
- `ISPIN`：含磁性元素只建议 `2`，仍需用户给初始磁矩并检查磁性收敛。
- `CSHIFT/NEDOS`：控制展宽和频率采样；默认值只是起点，不替代收敛测试。
- `material/prefix`：`auto` 从 POSCAR 元素和数量生成；用户可任意改名，不触发物理分支。

完整判据、适用性和局限见 [`references/parameter-decisions.md`](references/parameter-decisions.md)。

## 5. Workflow

### 5.1 检查和分类（不产生文件）

```bash
python scripts/config_loader.py --config config.yaml --inspect
python scripts/config_loader.py --config config.yaml --check
```

成功标志：第一条输出 `INSPECT=OK;NO_FILES_CREATED=true`；确认后第二条输出 `CHECK=OK`。失败标志统一为 `INPUT=INVALID;...` 或 `CHECK=FAIL;...`；修复后再继续。

### 5.2 准备两个运行目录

```bash
python scripts/prepare.py --config config.yaml
```

成功标志：`PREPARE=OK`，并生成 `<output_dir>/00_DFT`、`<output_dir>/01_LOPTICS`，每个目录有 POSCAR/POTCAR/KPOINTS 和脚本生成的 INCAR。输出目录已存在时拒绝覆盖；原始输入保持不变。

### 5.3 运行 DFT 和 LOPTICS

```bash
python scripts/run.py --config config.yaml
```

`run.py` 先做 oneAPI/MPI/VASP 配置检查，再运行 DFT；只有 DFT 返回零、`OUTCAR/WAVECAR/CHGCAR` 非空且有 `General timing and accounting` 才会把结果交给 LOPTICS。LOPTICS 必须有 `OUTCAR/vasprun.xml/WAVECAR/WAVEDER`、实部和虚部频率相关介电函数以及最终 timing。

成功标志是 `RUN=PASS`。任何失败都输出 `RUN=FAIL;原因` 并停止；不要手动跳过失败继续提取。常见原因及处理见 [`references/failure-handling.md`](references/failure-handling.md)。

### 5.4 提取能量域和绘图

```bash
python scripts/extract.py --config config.yaml
python scripts/plot.py --config config.yaml
```

`extract.py` 读取 `01_LOPTICS/vasprun.xml` 中配置的 `density-density` 块，取 xx/yy/zz 对角分量的平均值，再由复介电函数计算 `n`、`k`、`alpha_cm-1` 和法向入射 `reflectivity`。成功标志是 `EXTRACT=OK` 和 `CSV=..._optical_properties.csv`。

`plot.py` 将 `wavelength_nm = 1239.841984 / energy_eV`，去掉零能量点后按波长排序，生成波长域 CSV 和 9 张 PNG（6 个量、alpha 的线性/对数窗口图、R 窗口图）。成功标志是 `WAVELENGTH_POSTPROCESS=OK`。

### 5.5 只读验证和外部对照

```bash
python scripts/validate.py --config config.yaml
```

验证不运行 VASP、不删除、不覆盖任何文件。它检查输入产物、介电函数区块、响应类型、两份 CSV 的列和有限值、能量/波长严格递增、`n/k/alpha ≥ 0`、`0 ≤ R ≤ 1` 和所有图文件。成功标志必须是 `VALIDATION=PASS`；否则是 `VALIDATION=FAIL;原因`。

在线对照只用于合理性检查：搜索同组成、同晶相、同计算近似的权威数据，记录 URL/DOI、比较的带隙/峰位/介电常数和差异原因；不能代替收敛测试。模板见 [`references/online-validation.md`](references/online-validation.md)。

### 5.6 输入/输出契约（固定文件名）

运行后主要文件位于 `<output_dir>/01_LOPTICS/`：

- VASP 原始结果：`OUTCAR`、`vasprun.xml`、`WAVECAR`、`WAVEDER`。
- 能量域：`<prefix>_optical_properties.csv`。
- 波长域：`<prefix>_optical_properties_wavelength.csv`。
- 能量域图：`<prefix>_epsilon1.png`、`_epsilon2.png`、`_n.png`、`_k.png`、`_alpha.png`、`_R.png`。
- 波长域图：`<prefix>_eps1_vs_wavelength.png`、`_eps2_vs_wavelength.png`、`_n_vs_wavelength.png`、`_k_vs_wavelength.png`、`_alpha_vs_wavelength.png`、`_R_vs_wavelength.png`，以及 `_<300>_<2500>nm*.png` 窗口图。

两份 CSV 都含以下字段：`energy_eV`、`wavelength_nm`、`eps1_xx/yy/zz/xy/yz/zx`、`eps2_xx/yy/zz/xy/yz/zx`、`eps1_avg`、`eps2_avg`、`n`、`k`、`alpha_cm-1`、`reflectivity`。字段含义和读取优先级见 [`references/input-output-contract.md`](references/input-output-contract.md)。

### 5.7 可执行例子和反例

有效起点：

```bash
cp config.yaml.example config.yaml
python scripts/config_loader.py --config config.yaml --inspect
# 人工审阅后把 confirm_recommendations 改为 true，并确认 input_dir/output_dir
python scripts/prepare.py --config config.yaml
python scripts/run.py --config config.yaml
python scripts/extract.py --config config.yaml
python scripts/plot.py --config config.yaml
python scripts/validate.py --config config.yaml
```

边界例子：缺少 `POTCAR` 时应看到 `INPUT=INVALID;Missing input file`；确认仍为 false 时应看到 `PREPARE=FAIL;Confirmation required`；输出目录已存在时应看到 `refusing to overwrite`；检测为 metal、磁性候选、SOC 候选、slab/2D 或 molecule 候选时，先暂停并记录近似，不要只改 `material` 名称强行运行。

## 6. Common Pitfalls

- 没有 POTCAR、POTCAR 顺序与 POSCAR 不同、块数不同：停止，不能猜赝势。
- `ENCUT < max(ENMAX)` 或 KPOINTS 与配置不一致：修复后重新 `--inspect/--check`。
- 把几何分类当成电子结构结论；只有 DFT 才能确认带隙、费米面和磁矩。
- 磁性/SOC/金属/二维/分子候选仍使用普通三维、非磁、无 SOC 固定 INCAR：先确认物理近似。
- DFT 与 LOPTICS 的结构、赝势、K 点、NBANDS、ISPIN 不兼容：不要进入响应步骤。
- 空带不足、K 点过稀、CSHIFT/NEDOS 未收敛：只能报告为 demo 起始结果。
- `alpha_cm-1` 是吸收系数，不是有厚度后的吸收率；`reflectivity` 是法向入射界面反射率。
- 只看 PNG 不看 `OUTCAR`/`vasprun.xml`/CSV/验证报告；不要把 CSV 的 2000 行相加，曲线的每一行对应一个能量点。
- 不在已有结果目录上重跑；使用新的 `output_dir` 保留可追溯性。

## 7. Verification Checklist

- [ ] 三个输入文件存在、非空、可解析；POSCAR/POTCAR 元素顺序和块数一致。
- [ ] 已记录真实 `TITEL/ENMAX/ZVAL`、实际 K 点模式/网格/偏移和体系分类。
- [ ] 已识别电子性质不确定性、磁性/SOC/二维/分子风险，并由用户确认近似。
- [ ] `run.confirm_recommendations: true` 只在人工审阅后设置；输出目录未被覆盖。
- [ ] `ENCUT ≥ max(ENMAX)`，并计划 ENCUT/K 点/NBANDS/CSHIFT/NEDOS 收敛测试。
- [ ] DFT 有非空 `OUTCAR/WAVECAR/CHGCAR` 和 timing；LOPTICS 有非空 `OUTCAR/vasprun.xml/WAVEDER/WAVECAR`。
- [ ] LOPTICS `OUTCAR` 同时含 IMAGINARY/REAL DIELECTRIC FUNCTION 和 timing。
- [ ] 两份 CSV 都含完整字段；没有 NaN/Inf，能量和波长单调，`n/k/alpha ≥ 0`，`0 ≤ R ≤ 1`。
- [ ] 能量域和波长域的 epsilon1/epsilon2/n/k/alpha/R 图均存在。
- [ ] `validate.py` 输出 `VALIDATION=PASS`，并单独记录外部同体系对照来源。

版本说明：v0.5 在 v0.4 基础上补充了输入/输出契约、固定状态码、依赖和 Linux 边界、失败处理链接、正反例、统一术语及本版本变更记录；保留 v0.4 目录以便回退和比较。
