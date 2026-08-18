---
name: run-vasp-optics-adaptive-v0-7
description: "Use when a user supplies VASP POSCAR, POTCAR and KPOINTS and wants an independent-particle optical workflow that adapts by physical system type rather than material name. Inspect and preserve user choices, classify bulk/2D/1D/isolated geometry, run a ground state, classify metal/semiconductor/insulator from actual eigenvalues, require two review gates, run LOPTICS with explicit metal and non-bulk policies, extract epsilon/n/k/alpha/reflectivity/loss/conductivity, and require read-only validation."
---

# 自适应 VASP 光学工作流 v0.7

## 1. 目标与边界

严格按以下状态机执行：

`输入事实 → 结构类型 → 初始参数建议 → 用户确认 → 基态 DFT → 电子类型 → 用户确认 → LOPTICS → 后处理 → 验证`

不要用 SiC、Si、NaCl 等材料名称选择参数。`material` 和 `prefix` 只用于显示和文件名。

本技能覆盖独立粒子 `LOPTICS`。不自动处理结构弛豫、GW/BSE、局域场 `CHI`、声子/离子介电、激子、磁光或严格二维极化率。不得伪造 POTCAR、复用别的材料结果、覆盖旧输出或隐藏验证失败。

## 2. 输入事实和用户优先原则

必须存在：

| 文件 | 读取内容 | 硬检查 |
|---|---|---|
| `POSCAR` | 晶格、元素、计数、坐标模式 | 格式可解析 |
| `POTCAR` | 每块 `TITEL/ENMAX/ZVAL` | 块数和元素顺序与 POSCAR 一致 |
| `KPOINTS` | Gamma/Monkhorst 网格和偏移 | 三整数网格可解析 |

可选读取 `input_dir/INCAR`。当 `parameters.parameter_policy: preserve-user` 时，优先继承用户已有的泛函、DFT+U、磁性、SOC 等物理标签；技能只覆盖完成本阶段所必需的运行标签。若用户值与 POTCAR、电子类型或 LOPTICS 不兼容，先解释冲突，再请用户决定，不能静默替换。

本技能不下载、编译或猜测 POTCAR。不要把 POTCAR、API 密钥或私有路径提交到公共仓库。

字段契约见 [`references/input-output-contract.md`](references/input-output-contract.md)。术语、正例、反例、边界例和对外发送前的脱敏规则见 [`references/usage-examples-and-privacy.md`](references/usage-examples-and-privacy.md)。

VASP 阶段需要 Linux/Bash、GNU `timeout`、MPI 启动器、可执行 `vasp_std` 和集群要求的 oneAPI 环境。MPI 启动器必须与 VASP 链接的 MPI 库属于同一实现；Intel MPI 编译的 VASP 不能用 Open MPI 的 `/usr/bin/mpirun` 启动。若实际 KPOINTS 是严格 `1×1×1 Gamma`，配置可提供 `vasp_gamma_bin`，脚本按 KPOINTS 自动选择 `vasp_gam`；不得按材料名称选择。后处理环境需要 PyYAML、NumPy、pandas、matplotlib 和 lxml。依赖的获得方式、平台边界及安装责任见 [`references/platform-and-preflight.md`](references/platform-and-preflight.md)。

## 3. 两次分类

### 3.1 VASP 前：结构类型候选

仅根据晶格尺度和 K 点方向输出：

- `bulk-3d-candidate`
- `slab-or-2d-candidate`
- `wire-or-1d-candidate`
- `molecule-or-isolated-candidate`

这是候选分类，不是空间群证明。非体相体系的 VASP 三维介电函数随真空体积变化；只有用户设置 `allow_nonbulk_supercell_optics: true` 才可继续，并必须把结果标为“超胞依赖、非内禀体光学常数”。

### 3.2 基态后：电子类型

运行 `00_DFT` 后，用 `scripts/classify_electronic.py` 读取实际 `vasprun.xml` 的本征值、占据数和费米能级，生成 `system_classification.json`：

- `metal-or-semimetal`
- `semiconductor`
- `insulator`

POSCAR/POTCAR/KPOINTS 不能证明带隙，因此不要在 DFT 前把 `system_hint` 当作最终结论。分类阈值只用于工作流路由，不替代能带收敛或严谨物性定义。

## 4. 参数决策

- `KPOINTS`：实际运行保留用户文件；几何公式只给收敛对照候选。
- `ENCUT`：用户未给出时，从最大 `ENMAX` 向上取整到 10 eV；低于最大 `ENMAX` 时停止。
- `NBANDS`：按 `ZVAL × 原子数` 估计占据带并增加空带；DFT 和 LOPTICS 使用同一 NBANDS，避免 WAVECAR 能带数警告。定量光谱必须增加 NBANDS 做收敛。
- 有带隙候选：起点 `ISMEAR=0`、`SIGMA=0.01 eV`、`CSHIFT=0.10 eV`。
- 金属/半金属：必须选择 `stop`、`interband-only` 或 `drude`。`drude` 需要用户提供有物理依据的 `WPLASMAI>0`；不得自动猜散射宽度。
- `NEDOS=2000` 是起点；更改采样密度不等于提高物理精度。
- 磁性元素和重元素只触发审阅；不自动决定磁序、`MAGMOM` 或 SOC。

完整公式和分支见 [`references/parameter-decisions.md`](references/parameter-decisions.md)。

## 5. 固定执行流程

### 5.1 只读预检

```bash
python scripts/preflight.py --config config.yaml
python scripts/config_loader.py --config config.yaml --inspect
```

必须看到：

```text
PREFLIGHT=PASS
INSPECT=OK;NO_FILES_CREATED=true
```

向用户解释“输入事实、保留的用户值、技能建议、仍未知的电子类型”。用户同意后设置：

```yaml
run:
  confirm_recommendations: true
```

### 5.2 准备新目录

```bash
python scripts/config_loader.py --config config.yaml --check
python scripts/prepare.py --config config.yaml
```

必须使用不存在的 `output_dir`。成功标志为 `PREPARE=OK`。

### 5.3 基态 DFT 和第二闸门

```bash
python scripts/run.py --config config.yaml --stage dft
```

成功后应出现：

```text
DFT=PASS
CLASSIFY=OK 或 system_classification.json
RUN=PAUSED
```

读取并向用户解释 `structure_class`、`electronic_class`、估计带隙、分数占据和警告。确认后设置：

```yaml
run:
  confirm_electronic_classification: true
```

非体相还需显式设置 `allow_nonbulk_supercell_optics: true`。金属/半金属还需选择 `metal_optics_mode`；选择 `drude` 时填写 `parameters.loptics.wplasmai`。

### 5.4 LOPTICS

```bash
python scripts/run.py --config config.yaml --stage loptics
```

脚本重新生成最终 INCAR，复制同一套 POSCAR/POTCAR/KPOINTS 和基态 WAVECAR/CHGCAR，然后运行 VASP。必须检查：

- `OUTCAR/vasprun.xml/WAVECAR/WAVEDER` 非空；
- 实部、虚部 frequency-dependent dielectric function 均存在；
- `General timing and accounting` 存在。

成功标志为 `RUN=PASS`。

### 5.5 后处理和验证

```bash
python scripts/extract.py --config config.yaml
python scripts/plot.py --config config.yaml
python scripts/validate.py --config config.yaml
```

最终必须看到：

```text
EXTRACT=OK
WAVELENGTH_POSTPROCESS=OK
VALIDATION=PASS
```

## 6. 输出与解释

主要结果位于 `<output_dir>/01_LOPTICS/`：

- 原始结果：`OUTCAR`、`vasprun.xml`、`WAVECAR`、`WAVEDER`；
- 决策证据：`system_classification.json`、`<prefix>_optics_metadata.json`；
- 数据：能量域和波长域 CSV；
- 曲线：`eps1/eps2/n/k/alpha_cm-1/reflectivity/loss_function/sigma1_S_m` 的能量域和波长域 PNG；图文件可使用 `epsilon1/epsilon2/alpha/R/loss/sigma1` 显示别名。

CSV 中每一行是一个光子能量点，不要把所有行相加。主要派生量：

- `n/k`：由复介电函数平方根得到；
- `alpha_cm-1`：由角频率和 `k` 得到；
- `reflectivity`：法向入射 Fresnel 公式；
- `loss_function`：`Im[-1/epsilon]`；
- `sigma1_S_m`：`epsilon0 × omega × epsilon2`。

对于非体相，以上量保留为可复现的三维超胞结果，但不能直接称为二维或分子的内禀体光学常数。

## 7. 必须停止的情况

- 缺少或伪造 POTCAR；
- POSCAR/POTCAR 元素顺序不一致；
- 输出目录已存在或有部分旧输出；
- 尚未通过任一确认闸门；
- 金属检测后仍为 `metal_optics_mode: stop`；
- Drude 模式没有正的 `WPLASMAI`；
- 非体相没有确认超胞依赖；
- 磁性/SOC/DFT+U 标签互相不一致；
- VASP 非零退出、缺 timing、缺介电区块或缺 WAVEDER；
- `VALIDATION=FAIL`。

失败定位见 [`references/failure-handling.md`](references/failure-handling.md)。同体系外部对照见 [`references/online-validation.md`](references/online-validation.md)，只能做合理性检查，不能替代 ENCUT/KPOINTS/NBANDS/展宽收敛。

## 8. 完成检查清单

- [ ] 三个输入文件真实、顺序正确，用户 INCAR 的保留项已列明。
- [ ] 结构候选和风险已解释，第一次确认完成。
- [ ] 基态 DFT 完整，电子类型来自实际本征值，第二次确认完成。
- [ ] 金属或非体相使用了显式策略，没有材料名称硬编码。
- [ ] DFT/LOPTICS 使用兼容的 POTCAR、KPOINTS、ISPIN 和 NBANDS。
- [ ] 两份 CSV、16 张基础图、分类及元数据完整。
- [ ] `VALIDATION=PASS`，且局限性随结果交付。

## 9. 版本与变更

当前版本为 `v0.7`。变更记录和与旧版的差异见 [`references/version-history.md`](references/version-history.md)。修改分类阈值、参数公式、输出字段或安全边界时，必须同步更新该记录、配置示例和自动测试。
