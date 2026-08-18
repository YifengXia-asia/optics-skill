# 输入和输出契约

## 输入

`run.input_dir` 必须指向同一个目录。`POSCAR`、`POTCAR`、`KPOINTS` 是唯一的用户必需 VASP 输入；`config.yaml` 是流程控制文件，不替代这三个文件。

| 项目 | 类型/范围 | 由谁提供 | 失败时的含义 |
|---|---|---|---|
| `POSCAR` | VASP 4/5 文本；3 个晶格向量和正整数原子数 | 用户 | 无法判断晶胞、元素数量或体系维度 |
| `POTCAR` | 一个或多个连续赝势块；每块含 `TITEL/ENMAX/ZVAL` | 用户/管理员提供的官方 VASP 赝势库 | 无法确认元素、截止能量和价电子数 |
| `KPOINTS` | 显式 Gamma/Monkhorst-Pack 网格；三整数和可选偏移 | 用户 | 无法复现 Brillouin 区采样 |
| `INCAR`（可选） | 用户已有计算设置 | 用户 | 不影响最低三文件流程；存在时按策略继承物理标签 |
| `config.yaml` | YAML；路径、环境、参数和两次确认闸门 | 技能模板+用户审阅 | 无法决定是否允许准备/运行 |

### 配置字段类型

| YAML 路径 | 类型 | 允许值/约束 | 示例默认值 |
|---|---|---|---|
| `run.input_dir` | 字符串路径 | 必须包含三个输入文件 | `./inputs` |
| `run.output_dir` | 字符串路径 | 必须不存在；拒绝覆盖 | `./stage1_demo` |
| `run.material` | 字符串 | 只用于显示；`auto` 或任意用户标签 | `auto` |
| `run.prefix` | 字符串 | 只用于文件名；建议使用字母、数字、`_`、`-`、`.` | `auto` |
| `run.system_hint` | 枚举 | `auto`、`insulator`、`semiconductor`、`metal` | `auto` |
| `run.confirm_recommendations` | 布尔 | 未人工审阅时必须为 `false`；运行前必须为 `true` | `false` |
| `run.confirm_electronic_classification` | 布尔 | 基态分类审阅前为 `false` | `false` |
| `run.allow_nonbulk_supercell_optics` | 布尔 | 非体相明确接受超胞依赖后才能设为 `true` | `false` |
| `run.metal_optics_mode` | 枚举 | `stop`、`interband-only`、`drude` | `stop` |
| `environment.vasp_bin` | 字符串/路径 | PATH 中的命令或可执行绝对路径 | `vasp_std` |
| `environment.vasp_gamma_bin` | 字符串/路径 | 可选；仅 1×1×1 Gamma 输入自动选择 | 空 |
| `environment.auto_select_gamma` | 布尔 | 只根据实际 KPOINTS 决定是否使用 vasp_gam | `true` |
| `environment.mpi_launcher` | 字符串/路径 | PATH 中的 MPI 启动器或可执行路径 | `mpirun` |
| `environment.mpi_cores` | 正整数 | 集群允许的 MPI 进程数 | `4` |
| `environment.timeout_seconds` | 正整数 | 单步 VASP 超时时间 | `3600` |
| `parameters.encut` | `auto` 或数值 | 数值不得低于 POTCAR 最大 ENMAX | `auto` |
| `parameters.nbands` | `auto` 或正整数 | 应覆盖目标能量窗口并收敛 | `auto` |
| `parameters.response` | 枚举 | 当前支持 `density-density` | `density-density` |
| `parameters.parameter_policy` | 枚举 | `preserve-user` 或 `skill-only` | `preserve-user` |
| `parameters.heuristics.*` | 正数 | ENCUT 取整、K 点对照密度和 NBANDS 空带余量的可审阅起点 | 见 `config.yaml.example` |
| `parameters.loptics.wplasmai` | 非负数 | 仅 Drude 分支要求大于 0；不得自动猜测 | `0.0` |
| `postprocess.wavelength_constant_nm_eV` | 正数 | 波长换算常数；通常不改 | `1239.841984` |
| `postprocess.plot_min_nm`/`plot_max_nm` | 非负数 | `plot_max_nm > plot_min_nm` | `300`/`2500` |
| `classification.vacuum_axis_min_angstrom` 等 | 正数 | 只控制结构候选路由，不代表真空或物性已收敛 | `6.0`、`1.8`、`2.5`、`10.0` |

## CSV 字段

`<prefix>_optical_properties.csv` 的一行对应一个光子能量点，不是把 2000 行相加。`plot.py` 重新计算波长并排序后写出 `<prefix>_optical_properties_wavelength.csv`。

- `energy_eV`：VASP 频率网格的光子能量。
- `wavelength_nm`：由 `postprocess.wavelength_constant_nm_eV / energy_eV` 得到；零能量行应为空/NaN。
- `eps1_*`、`eps2_*`：复介电张量实部/虚部的 xx、yy、zz、xy、yz、zx 分量，直接来自 `vasprun.xml` 的 `real/imag` 数组。
- `eps1_avg`、`eps2_avg`：xx、yy、zz 三个对角分量的算术平均，用于后续各向同性曲线。
- `n`、`k`：由平均复介电函数计算的折射率和消光系数。
- `alpha_cm-1`：由 `k` 和角频率得到的吸收系数，单位 cm⁻¹；不是给定厚度后的吸收率。
- `reflectivity`：由 `n`、`k` 计算的法向入射界面反射率，理论检查范围为 0–1。
- `loss_function`：由平均复介电函数得到的 `Im[-1/epsilon]`。
- `sigma1_S_m`：由 `epsilon0 × omega × epsilon2` 得到的实部光学电导率，单位 S/m。

`system_classification.json` 保存基态本征值分类依据；`<prefix>_optics_metadata.json` 保存体相/非体相归一化标签和金属处理模式。两者必须与 CSV 一起交付。

## 应该先看什么

1. 先看 `validate.py` 的 `VALIDATION=PASS`。
2. 再看 CSV 的列名、能量/波长范围和数值范围。
3. 再看 `OUTCAR` 的两段频率相关介电函数和最终 timing。
4. 最后看 PNG 的峰位和趋势。PNG 只用于可视化，不能替代 CSV 数值。
