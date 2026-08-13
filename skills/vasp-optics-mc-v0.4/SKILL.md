---
name: vasp-optics-mc-v0-4
description: "Use when a user provides VASP POSCAR, POTCAR and KPOINTS and needs a system-adaptive independent-particle optical workflow: classify the structure from the actual inputs, recommend parameters for review, wait for explicit confirmation, run DFT then LOPTICS, extract epsilon1/epsilon2/n/k/alpha/reflectivity, and validate energy- and wavelength-domain outputs."
---

# VASP 体系自适应独立粒子光学工作流 v0.4

## 1. Overview

按照下面的固定顺序完成任务：

`POSCAR + POTCAR + KPOINTS → 体系分类 → 参数建议 → 用户确认 → DFT → LOPTICS → vasprun.xml 解析 → 能量/波长 CSV 与图 → 只读验证`

使用真实输入文件决定体系，而不要使用材料名称作为开关。材料名称和前缀只用于显示和输出文件名。`scripts/config_loader.py` 会读取晶格长度、元素顺序、POTCAR 的 ENMAX/ZVAL、K 点网格，并报告：

- 结构候选：三维体相、二维/表面候选、分子/孤立体系候选；
- 电子性质：用户明确给出的绝缘体/半导体/金属，或“需要 DFT 确认”；
- 磁性元素和重元素警告；
- ENCUT、NBANDS、KPOINTS、ISMEAR、ISPIN、CSHIFT 的起始建议及理由。

自动建议不是收敛证明。只有用户审阅建议并将 `run.confirm_recommendations` 改为 `true` 后，才允许创建运行目录。详细判据见 [`references/parameter-decisions.md`](references/parameter-decisions.md)，在线同体系对照见 [`references/online-validation.md`](references/online-validation.md)。

## 2. When to Use

在用户希望把已有 VASP 基态结果接到 `LOPTICS`，并需要 `epsilon1/epsilon2/n/k/alpha/reflectivity` 及其能量、波长曲线时使用本技能。默认范围是独立粒子、非 GW/BSE 的光学响应。

遇到以下情况先暂停并要求单独方案：结构弛豫、GW/BSE、SOC、强磁性、自旋轨道耦合、金属费米面光学、声子/离子介电响应、局域场效应、分子/二维体系的特殊介电归一化。分类器可以识别这些风险，但不会假装它们已经被本技能正确处理。

## 3. Prerequisites

1. 要求用户在同一个输入目录提供 `POSCAR`、`POTCAR`、`KPOINTS`。本技能不生成赝势，也不替用户编译 `POTCAR`。
2. 要求 `POTCAR` 的元素块顺序与 `POSCAR` 一致；从实际 `POTCAR` 读取 `TITEL`、`ENMAX` 和 `ZVAL`。
3. 要求可用的 `vasp_std`、MPI 和必要的 oneAPI/MKL 环境；运行前先做环境自检。
4. 要求后处理环境能导入 PyYAML、NumPy、SciPy、pandas、matplotlib 和 lxml。
5. 要求输出目录不存在。脚本拒绝覆盖旧目录，原始输入和已有结果保持不变。

## 4. Configuration and Parameter Policy

复制 `config.yaml.example` 为 `config.yaml`，先保留 `auto`，再执行：

```bash
python scripts/config_loader.py --config config.yaml --inspect
```

`--inspect` 只读，不创建文件。审阅输出中的 `STRUCTURE_CLASS`、`ELECTRONIC_CHARACTER` 和 `RECOMMENDED`，必要时修改参数或填写 `system_hint`，然后把：

```yaml
run:
  confirm_recommendations: true
```

显式改为 `true`。这一步是执行闸门，不是材料名称匹配。

决策规则如下：

- `ENCUT`：由实际 `POTCAR` 的最大 `ENMAX` 向上取整到 10 eV；显式值低于最大 `ENMAX` 时阻止准备。
- `KPOINTS`：依据晶格长度估算起始网格；疑似真空方向设为 1。脚本不会自动改写用户的 `KPOINTS`，显式网格与输入不一致时报告错误。
- `NBANDS`：使用 `ZVAL × 原子数` 估算占据带，再加空带余量；目标光子能量越高，空带越多，并必须做收敛测试。
- `ISMEAR/SIGMA`：用户明确指定电子性质时按其类别给起始值；未知时标记“需先检查 DFT”，不能把未知体系宣称为半导体。
- `ISPIN`：检测到磁性元素只给 `ISPIN=2` 的候选建议，并要求用户提供初始磁矩和收敛判断。
- `CSHIFT`、`NEDOS`：分别控制展宽和频率网格；它们是起始值，不替代展宽/频率收敛测试。
- `material`、`prefix`：`auto` 时从实际元素和数量生成显示式；用户可任意改名，不改变物理输入。

如果分类结果为金属、磁性候选、重元素 SOC 候选、二维/表面候选或分子候选，必须在确认前写清楚采用的物理近似和不适用项。不要只替换材料名字继续运行。

## 5. Workflow

### 5.1 分类和审阅

```bash
python scripts/config_loader.py --config config.yaml --inspect
python scripts/config_loader.py --config config.yaml --check
```

第一条命令给出分类和建议；第二条命令只有在确认标志为 `true` 且输出目录为空时才通过。失败时先修复输入或配置，不运行 VASP。

### 5.2 准备 DFT 和 LOPTICS 目录

```bash
python scripts/prepare.py --config config.yaml
```

脚本创建 `<output_dir>/00_DFT` 和 `<output_dir>/01_LOPTICS`，复制三份输入文件，并生成两份明确的 `INCAR`。它不会修改原始输入。

### 5.3 运行 VASP

```bash
python scripts/run.py --config config.yaml
```

先运行 DFT，确认 `OUTCAR`、`WAVECAR`、`CHGCAR` 非空且没有明显错误；再将 DFT 产生的电荷/波函数用于 LOPTICS。LOPTICS 阶段应产生 `OUTCAR`、`vasprun.xml`、`WAVECAR` 和 `WAVEDER`。不要把 GW、BSE 或声子响应的结果冒充为本流程结果。

### 5.4 提取和绘图

```bash
python scripts/extract.py --config config.yaml
python scripts/plot.py --config config.yaml
```

提取脚本读取 `vasprun.xml` 中配置指定的 `density-density` 响应，得到各向异性的 `eps1_xx/yy/zz`、`eps2_xx/yy/zz`，并计算平均值、`n`、`k`、`alpha_cm-1` 和反射率。绘图脚本用 `wavelength_nm = 1239.841984 / energy_eV` 生成波长域 CSV 和曲线，因此吸收系数与反射率对波长的函数也会输出。

### 5.5 只读验证和外部对照

```bash
python scripts/validate.py --config config.yaml
```

验证脚本不运行 VASP、不删除文件、不修改结果。它检查文件完整性、响应类型、介电函数、CSV 列、数值有限性、能量/波长排序、`n/k/alpha` 非负、`0 ≤ R ≤ 1` 以及图文件。随后按 [`references/online-validation.md`](references/online-validation.md) 搜索同组成、同晶相、同计算近似的权威资料，并在报告中记录 URL/DOI、比较量和差异原因；外部数据只能做合理性对照，不能替代收敛测试。

## 6. Common Pitfalls

- 缺少 `POTCAR` 或手工拼错元素顺序：停止，不要用别的材料赝势顶替。
- `ENCUT < max(ENMAX)`：提高或明确记录有意的收敛测试计划。
- 把别的晶胞的 K 点网格直接复制过来：按晶格长度和维度重新审阅。
- 仅凭元素名称断言“金属/半导体/磁性”：这些判断需要 DFT 或用户物理信息。
- 磁性或 SOC 候选仍使用非磁、无 SOC 的固定 INCAR：在确认阶段暂停并说明近似。
- DFT 与 LOPTICS 的 POSCAR/POTCAR/KPOINTS、NBANDS、ISPIN 不兼容：不要进入响应步骤。
- 空带不足导致高能区曲线不完整：提高 `NBANDS` 并比较收敛结果。
- 把 `alpha_cm-1` 当成样品吸收率：吸收率还需要厚度和光学几何。
- 只看一张图判断成功：同时检查 OUTCAR、vasprun.xml、CSV、数值范围和验证报告。
- 直接覆盖已有结果：改用新 `output_dir`，保留旧结果作为可追溯证据。

## 7. Verification Checklist

- [ ] `POSCAR`、`POTCAR`、`KPOINTS` 存在且可读。
- [ ] POSCAR/POTCAR 元素顺序和元素块数量一致。
- [ ] 已记录实际 POTCAR 的 `TITEL/ENMAX/ZVAL`。
- [ ] 已输出结构类别、电子性质不确定性、磁性/SOC 警告。
- [ ] 用户已审阅建议并设置 `confirm_recommendations: true`。
- [ ] `ENCUT` 不低于最大 `ENMAX`，且已有收敛测试计划。
- [ ] KPOINTS 与晶胞维度、Gamma/Monkhorst 模式和偏移一致。
- [ ] DFT 有非空 `OUTCAR/WAVECAR/CHGCAR`。
- [ ] LOPTICS 有非空 `OUTCAR/vasprun.xml/WAVEDER`。
- [ ] OUTCAR 含实部和虚部频率相关介电函数及最终 timing。
- [ ] 能量域、波长域 CSV 均含 `epsilon1/epsilon2/n/k/alpha/reflectivity`。
- [ ] `alpha(lambda)` 与 `R(lambda)` 图存在，且数值范围合理。
- [ ] `validate.py` 输出 `VALIDATION=PASS`。
- [ ] 已完成同组成/同晶相/同近似的在线权威资料对照，并记录出处。
