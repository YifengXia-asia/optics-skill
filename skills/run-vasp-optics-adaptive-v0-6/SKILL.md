---
name: run-vasp-optics-adaptive-v0-6
description: "Use when a user provides POSCAR, POTCAR and KPOINTS and needs a system-adaptive VASP independent-particle optical workflow. Preflight the Linux/MPI/Python environment, classify the actual input system, recommend reviewable parameters, require explicit confirmation, run DFT then LOPTICS, extract epsilon/n/k/alpha/reflectivity in energy and wavelength domains, and stop on incomplete or unsafe inputs."
---

# 自适应 VASP 光学计算工作流 v0.6

## 1. 目标和边界

按以下顺序执行，不跳步：

`输入预检 → 体系分类 → 参数建议 → 用户确认 → DFT → LOPTICS → XML 提取 → 波长后处理 → 只读验证`

本技能只处理独立粒子、无 GW/BSE、无 SOC、无声子/离子介电响应的阶段一光学计算。不要把材料名称当作参数开关；分类只依据 POSCAR、POTCAR、KPOINTS 的实际内容。`material` 和 `prefix` 只控制显示及文件名。

遇到结构弛豫、GW/BSE、SOC、强磁性、金属费米面光学、声子响应、局域场效应、二维/分子真空归一化等请求，先暂停并要求单独方案。不得伪造缺失结果、跳过验证、用别的材料输出冒充当前材料，或在用户未确认时覆盖旧目录。

## 2. 输入契约

要求 `run.input_dir` 中有三个非空、可读的普通文件：

| 文件 | 必须内容 | 必须检查 |
|---|---|---|
| `POSCAR` | VASP 4/5 格式；晶格矢量、原子数；VASP 5 应有元素名 | 可解析晶格和计数；元素顺序用于和 POTCAR 对照 |
| `POTCAR` | 与 POSCAR 元素顺序一致的真实连续赝势块 | 每块读取 `TITEL`、`ENMAX`、`ZVAL`；顺序和块数一致 |
| `KPOINTS` | 显式 Gamma 或 Monkhorst-Pack 三整数网格和偏移 | 模式、网格、偏移可解析；与显式配置一致 |

本技能不下载、编译或猜测 POTCAR。没有真实 POTCAR 时停止。输入字段的类型、范围和示例见 [`references/input-output-contract.md`](references/input-output-contract.md)。

## 3. 环境契约和跨平台边界

### 3.1 支持矩阵

| 平台 | 预检/提取/绘图/验证 | VASP 运行 |
|---|---|---|
| Linux + Bash + GNU coreutils | 支持 | 支持，需可用 VASP、MPI、oneAPI/MKL（若集群要求） |
| WSL2 | 支持 | 仅当 WSL 内已安装可执行 VASP 和 MPI |
| macOS | 支持；需 Python 依赖 | 只有自行编译 VASP、MPI 和 GNU `timeout` 后才支持 |
| 原生 Windows | 可在 Python 环境中做静态后处理 | 不支持 `run.py`；使用 WSL 或远程 Linux |

### 3.2 必须预检的依赖

VASP 阶段需要 `bash`、`timeout`、`mpirun`、可执行 `vasp_std`，以及可选的 oneAPI setup 文件。后处理需要 Python 3.10+、PyYAML、NumPy、pandas、matplotlib；XML 读取使用 Python 标准库 `xml.etree.ElementTree`。`lxml` 可安装但不是本版本硬依赖。

不要假设 `conda_env` 会自动激活；它只是记录信息，必须由用户在运行前激活环境或在配置中给出解释器的绝对路径。路径可以是绝对路径，也可以是相对于当前工作目录的路径；不要把 `~` 当作脚本会自动展开的配置值。

## 4. 配置和参数契约

复制 `config.yaml.example` 为 `config.yaml`，按字段类型填写。所有用户可调值集中在配置中；脚本中的物理常数和文件命名规则不作为材料参数。

先运行环境预检和只读分类：

```bash
python scripts/preflight.py --config config.yaml
python scripts/config_loader.py --config config.yaml --inspect
```

只有看到 `PREFLIGHT=PASS` 和 `INSPECT=OK;NO_FILES_CREATED=true`，才审阅建议并把 `run.confirm_recommendations` 改为 `true`。`check` 和 `prepare.py` 在确认前必须失败。

核心决策：

- `ENCUT`：从实际 POTCAR 最大 `ENMAX` 向上取整到 10 eV；显式值低于最大 `ENMAX` 时失败。
- `KPOINTS`：按晶格长度和疑似真空方向估算起始网格；不会改写用户的 KPOINTS。
- `NBANDS`：由 `ZVAL × 原子数` 估算占据带并增加空带；目标能量越高越应增加并收敛测试。
- `ISMEAR/SIGMA`：`system_hint` 为 `insulator`、`semiconductor` 或 `metal` 时给起始建议；未知时标记 `unknown-needs-dft-check`。
- `ISPIN`：发现磁性元素只建议 `2`，仍需用户提供初始磁矩并检查收敛。
- `CSHIFT/NEDOS`：控制展宽和频率采样，只是起始值。
- `material/prefix`：`auto` 从 POSCAR 元素和计数生成；可任意改名，不改变计算分支。

详细判据见 [`references/parameter-decisions.md`](references/parameter-decisions.md)。

## 5. 固定执行流程

### 5.1 预检和分类（只读）

```bash
python scripts/preflight.py --config config.yaml
python scripts/config_loader.py --config config.yaml --inspect
python scripts/config_loader.py --config config.yaml --check
```

预检检查平台、Python 包、VASP/MPI/oneAPI 路径和三个输入文件；只读检查不创建运行目录。`--check` 成功标志为 `CHECK=OK`。任意失败都必须先修复，不运行 VASP。

### 5.2 准备 DFT 和 LOPTICS

```bash
python scripts/prepare.py --config config.yaml
```

成功标志为 `PREPARE=OK`。脚本创建 `<output_dir>/00_DFT` 和 `<output_dir>/01_LOPTICS`，复制三份输入并生成 INCAR；若输出目录已存在则拒绝覆盖。

### 5.3 运行 VASP

```bash
python scripts/run.py --config config.yaml
```

脚本先再次检查 VASP/MPI/oneAPI；DFT 必须返回零、产生非空 `OUTCAR/WAVECAR/CHGCAR` 并含 `General timing and accounting`，才把电荷和波函数交给 LOPTICS。LOPTICS 必须产生非空 `OUTCAR/vasprun.xml/WAVECAR/WAVEDER`，并同时含频率相关实部、虚部介电函数和最终 timing。

成功标志为 `RUN=PASS`。失败标志为 `RUN=FAIL;原因`，不得手动跳过。处理表见 [`references/failure-handling.md`](references/failure-handling.md)。

### 5.4 提取和波长后处理

```bash
python scripts/extract.py --config config.yaml
python scripts/plot.py --config config.yaml
```

`extract.py` 读取 `vasprun.xml` 中配置的 `density-density` 响应，使用 xx/yy/zz 对角分量平均值计算 `n`、`k`、`alpha_cm-1` 和法向入射 `reflectivity`。成功标志为 `EXTRACT=OK`。

`plot.py` 使用配置中的 `wavelength_constant_nm_eV`、`plot_min_nm` 和 `plot_max_nm` 将能量转换为波长、排序并生成 PNG。成功标志为 `WAVELENGTH_POSTPROCESS=OK`。

### 5.5 只读验证

```bash
python scripts/validate.py --config config.yaml
```

验证不运行 VASP、不删除、不覆盖文件。它检查 VASP 产物、介电函数区块、响应类型、两份 CSV 的字段和有限值、能量/波长单调性、`n/k/alpha ≥ 0`、`0 ≤ reflectivity ≤ 1` 以及能量域/波长域 PNG。最终必须看到 `VALIDATION=PASS`。

在线同体系对照只用于合理性检查，不替代收敛测试；按 [`references/online-validation.md`](references/online-validation.md) 记录来源、比较量和差异原因。

## 6. 输出契约和统一术语

主要输出位于 `<output_dir>/01_LOPTICS/`：

- 原始 VASP 产物：`OUTCAR`、`vasprun.xml`、`WAVECAR`、`WAVEDER`。
- 能量域 CSV：`<prefix>_optical_properties.csv`。
- 波长域 CSV：`<prefix>_optical_properties_wavelength.csv`。
- 能量域图：`<prefix>_epsilon1.png`、`_epsilon2.png`、`_n.png`、`_k.png`、`_alpha.png`、`_R.png`。
- 波长域图：`<prefix>_eps1_vs_wavelength.png`、`_eps2_vs_wavelength.png`、`_n_vs_wavelength.png`、`_k_vs_wavelength.png`、`_alpha_vs_wavelength.png`、`_R_vs_wavelength.png`，以及配置窗口对应的 alpha/R 图。

CSV 的 canonical 字段是：`energy_eV`、`wavelength_nm`、`eps1_xx/yy/zz/xy/yz/zx`、`eps2_xx/yy/zz/xy/yz/zx`、`eps1_avg`、`eps2_avg`、`n`、`k`、`alpha_cm-1`、`reflectivity`。

统一约定：

| 人类说法 | CSV canonical 字段 | PNG/显示别名 |
|---|---|---|
| 实部介电函数 | `eps1_*`、`eps1_avg` | `epsilon1`、`eps1` |
| 虚部介电函数 | `eps2_*`、`eps2_avg` | `epsilon2`、`eps2` |
| 吸收系数 | `alpha_cm-1` | `alpha` |
| 反射率 | `reflectivity` | `R` |

每行代表一个能量点；不要把 2000 行相加。字段来源、类型和读取优先级见 [`references/input-output-contract.md`](references/input-output-contract.md)。

## 7. 可执行正例、反例和停止条件

有效顺序：

```bash
cp config.yaml.example config.yaml
python scripts/preflight.py --config config.yaml
python scripts/config_loader.py --config config.yaml --inspect
# 人工确认建议，并设置 confirm_recommendations: true
python scripts/config_loader.py --config config.yaml --check
python scripts/prepare.py --config config.yaml
python scripts/run.py --config config.yaml
python scripts/extract.py --config config.yaml
python scripts/plot.py --config config.yaml
python scripts/validate.py --config config.yaml
```

必须停止的例子：

- 缺少 `POTCAR`：输出 `INPUT=INVALID;Missing input file`，要求用户提供真实赝势。
- `oneapi_setup` 仍为 `<absolute-path-to-oneapi-setvars.sh>`：输出 `PREFLIGHT=FAIL`，要求填写真实路径或清空该字段并确认环境已加载。
- `confirm_recommendations: false`：输出 `CHECK=FAIL` 或 `PREPARE=FAIL;Confirmation required`，不创建目录。
- `output_dir` 已存在：输出 `refusing to overwrite`，改用新目录。
- `plot_min_nm: 1800` 且 `plot_max_nm: 300`：输出 `PREFLIGHT=FAIL;Invalid postprocess wavelength...`，交换边界或改用合适的光谱窗口。
- 显式 `parameters.nbands` 小于预检估计的占据带数：输出 `PREFLIGHT=FAIL;parameters.nbands...below estimated occupied bands`，增加 NBANDS；高能窗口还要做空带收敛。
- `parameters.response: current-current`：输出 `PREFLIGHT=FAIL;parameters.response must be density-density`，阶段一只接受 `density-density`。
- VASP 4 POSCAR 没有元素名但 POTCAR 顺序正确：允许继续；若 POTCAR 也无法读取 TITEL，则输出 `INPUT=INVALID` 并停止。
- 检测为 metal、磁性、SOC、slab/2D 或 molecule 候选：先记录近似和用户决定，不只修改材料名称后运行。
- 用户要求“缺结果时复制别的材料结果”或“隐藏 VALIDATION=FAIL”：拒绝并说明结果不可追溯。

边界测试表（用于验证配置分支，而不是运行 VASP）：

| 测试输入 | 预期状态 | 修复/结论 |
|---|---|---|
| `plot_min_nm: 1800`、`plot_max_nm: 300` | `PREFLIGHT=FAIL` | 交换窗口边界 |
| 显式 `nbands` 小于预检的占据带估计 | `PREFLIGHT=FAIL` | 增加 NBANDS，并做空带收敛 |
| `response: current-current` | `PREFLIGHT=FAIL` | 阶段一改为 `density-density` |
| POSCAR VASP4 无元素名，但 POTCAR 有正确 TITEL 顺序 | `PREFLIGHT=PASS` 后可 `INSPECT=OK` | 允许；元素由 POTCAR 补充 |
| bulk 晶胞使用 `[1,1,1]` K 点 | `INSPECT` 给出稀疏采样风险 | 不自动改写；人工做 K 点收敛 |
| 含重元素或磁性元素 | `INSPECT=OK` 但出现风险建议 | 确认 SOC/ISPIN/初始磁矩后再决定是否继续 |

对不可接受请求使用固定拒绝边界：

| 请求 | 回复和动作 |
|---|---|
| “把别的材料的 OUTCAR/CSV 改名成当前结果” | 拒绝；说明结果不可追溯，不复制或改名 |
| “删除失败行，让验证变成 PASS” | 拒绝；保留失败原件，要求修复上游 |
| “把 API 密钥、POTCAR 或私有路径上传到公共仓库” | 拒绝；移除凭据并改用脱敏报告 |
| “未经确认直接覆盖目录或执行任意清理命令” | 拒绝；要求新 output_dir 和明确的最小范围操作 |
| “绕过 VASP 许可、权限或集群安全限制” | 拒绝；只提供合规的环境检查和管理员沟通建议 |

## 8. 检查清单和版本记录

- [ ] `PREFLIGHT=PASS`；平台和依赖与配置一致。
- [ ] POSCAR/POTCAR/KPOINTS 存在、可解析；元素顺序和 POTCAR 块数一致。
- [ ] 已记录 `TITEL/ENMAX/ZVAL`、K 点模式/网格/偏移和体系分类。
- [ ] 已审阅电子性质、磁性、SOC、二维/分子风险，并设置确认闸门。
- [ ] `ENCUT ≥ max(ENMAX)`，并计划 ENCUT/K 点/NBANDS/CSHIFT/NEDOS 收敛测试。
- [ ] DFT/LOPTICS 产物、介电函数区块和 timing 完整。
- [ ] 能量域和波长域 CSV 字段、数值范围和 PNG 完整。
- [ ] `VALIDATION=PASS`；已单独记录同体系外部对照。

v0.6 相比 v0.5：增加 `preflight.py` 环境预检；把波长常数和绘图窗口外置到配置；补充平台矩阵、字段类型/别名、反例及拒绝模板；统一 `eps1/eps2/alpha_cm-1/reflectivity` 术语；保留 v0.5 目录以便回退。详细记录见 [`references/version-history.md`](references/version-history.md)。
