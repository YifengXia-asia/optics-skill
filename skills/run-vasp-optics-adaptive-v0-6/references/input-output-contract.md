# 输入和输出契约

## 输入

`run.input_dir` 必须指向同一个目录。`POSCAR`、`POTCAR`、`KPOINTS` 是唯一的用户必需 VASP 输入；`config.yaml` 是流程控制文件，不替代这三个文件。

| 项目 | 类型/范围 | 由谁提供 | 失败时的含义 |
|---|---|---|---|
| `POSCAR` | VASP 4/5 文本；3 个晶格向量和正整数原子数 | 用户 | 无法判断晶胞、元素数量或体系维度 |
| `POTCAR` | 一个或多个连续赝势块；每块含 `TITEL/ENMAX/ZVAL` | 用户/管理员提供的官方 VASP 赝势库 | 无法确认元素、截止能量和价电子数 |
| `KPOINTS` | 显式 Gamma/Monkhorst-Pack 网格；三整数和可选偏移 | 用户 | 无法复现 Brillouin 区采样 |
| `config.yaml` | YAML；路径、环境、参数和确认闸门 | 技能模板+用户审阅 | 无法决定是否允许准备/运行 |

### 配置字段类型

| YAML 路径 | 类型 | 允许值/约束 | 示例默认值 |
|---|---|---|---|
| `run.input_dir` | 字符串路径 | 必须包含三个输入文件 | `./inputs` |
| `run.output_dir` | 字符串路径 | 必须不存在；拒绝覆盖 | `./stage1_demo` |
| `run.material` | 字符串 | 只用于显示；`auto` 或任意用户标签 | `auto` |
| `run.prefix` | 字符串 | 只用于文件名；建议使用字母、数字、`_`、`-`、`.` | `auto` |
| `run.system_hint` | 枚举 | `auto`、`insulator`、`semiconductor`、`metal` | `auto` |
| `run.confirm_recommendations` | 布尔 | 未人工审阅时必须为 `false`；运行前必须为 `true` | `false` |
| `environment.vasp_bin` | 字符串/路径 | PATH 中的命令或可执行绝对路径 | `vasp_std` |
| `environment.mpi_launcher` | 字符串/路径 | PATH 中的 MPI 启动器或可执行路径 | `mpirun` |
| `environment.mpi_cores` | 正整数 | 集群允许的 MPI 进程数 | `4` |
| `environment.timeout_seconds` | 正整数 | 单步 VASP 超时时间 | `3600` |
| `parameters.encut` | `auto` 或数值 | 数值不得低于 POTCAR 最大 ENMAX | `auto` |
| `parameters.nbands` | `auto` 或正整数 | 应覆盖目标能量窗口并收敛 | `auto` |
| `parameters.response` | 枚举 | 当前支持 `density-density` | `density-density` |
| `postprocess.wavelength_constant_nm_eV` | 正数 | 波长换算常数；通常不改 | `1239.841984` |
| `postprocess.plot_min_nm`/`plot_max_nm` | 非负数 | `plot_max_nm > plot_min_nm` | `300`/`2500` |

## CSV 字段

`<prefix>_optical_properties.csv` 的一行对应一个光子能量点，不是把 2000 行相加。`plot.py` 重新计算波长并排序后写出 `<prefix>_optical_properties_wavelength.csv`。

- `energy_eV`：VASP 频率网格的光子能量。
- `wavelength_nm`：由 `postprocess.wavelength_constant_nm_eV / energy_eV` 得到；零能量行应为空/NaN。
- `eps1_*`、`eps2_*`：复介电张量实部/虚部的 xx、yy、zz、xy、yz、zx 分量，直接来自 `vasprun.xml` 的 `real/imag` 数组。
- `eps1_avg`、`eps2_avg`：xx、yy、zz 三个对角分量的算术平均，用于后续各向同性曲线。
- `n`、`k`：由平均复介电函数计算的折射率和消光系数。
- `alpha_cm-1`：由 `k` 和角频率得到的吸收系数，单位 cm⁻¹；不是给定厚度后的吸收率。
- `reflectivity`：由 `n`、`k` 计算的法向入射界面反射率，理论检查范围为 0–1。

## 应该先看什么

1. 先看 `validate.py` 的 `VALIDATION=PASS`。
2. 再看 CSV 的列名、能量/波长范围和数值范围。
3. 再看 `OUTCAR` 的两段频率相关介电函数和最终 timing。
4. 最后看 PNG 的峰位和趋势。PNG 只用于可视化，不能替代 CSV 数值。
