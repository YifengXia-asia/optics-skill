# 使用示例、术语和脱敏规则

## 术语表

| 术语 | 简单含义 |
|---|---|
| `structure_class` | 由晶格长度和 K 点方向得到的结构候选，不是材料名称或空间群结论 |
| `electronic_class` | 基态 DFT 后从实际本征值和占据数得到的金属/半导体/绝缘体候选 |
| `metal-or-semimetal` | 存在分数占据、能带穿越费米能级或估计带隙接近零 |
| `confirm_recommendations` | 第一次确认：用户已经看过输入事实和起始参数建议 |
| `confirm_electronic_classification` | 第二次确认：用户已经看过基态电子分类，允许进入 LOPTICS |
| `interband-only` | 只保留 VASP LOPTICS 的带间响应，不声称包含完整金属低频 Drude 响应 |
| `drude` | 用户提供有依据的 `WPLASMAI` 后采用的金属低频处理分支 |
| `intrinsic_bulk_optics` | 是否可把结果按三维体相内禀光学常数解释；非体相超胞必须为 `false` |
| `response=density-density` | 从 `vasprun.xml` 中同名介电响应块读取实部和虚部 |

输出采用以下规范名；短写只作为图文件显示别名，不代表不同物理量：

| 规范名 | 允许的显示别名 |
|---|---|
| `eps1` / `eps2` | `epsilon1` / `epsilon2` |
| `alpha_cm-1` | `alpha` |
| `reflectivity` | `R` |
| `loss_function` | `loss` |
| `sigma1_S_m` | `sigma1` |

## 明确正例

用户提供同一体系的 `POSCAR/POTCAR/KPOINTS`，`output_dir` 不存在，Intel MPI 编译的 VASP 配置 oneAPI `mpirun`。先运行预检和 inspect，用户确认建议后运行 DFT；读取 `system_classification.json`，第二次确认后再运行 LOPTICS、提取、绘图和验证。只有出现 `VALIDATION=PASS` 才交付。

## 明确反例

以下做法是错误的，必须拒绝：

- **错误：** 因文件名含 `SiC` 就直接套用 SiC 参数。**正确：** 只从输入事实、用户 INCAR 和实际 DFT 结果决策。
- **错误：** 用 `/usr/bin/mpirun` 启动链接 Intel MPI 的 VASP。**正确：** 预检失败并改用同一 MPI 实现。
- **错误：** 输出目录已经存在仍继续准备。**正确：** 保留旧目录，选择新的 `output_dir`。
- **错误：** 金属分类后仍用 `metal_optics_mode: stop` 直接算。**正确：** 用户明确选择 `interband-only` 或提供有依据的 Drude 参数。
- **错误：** 把非体相超胞的 `epsilon/n/k/alpha/R` 称为内禀二维或分子常数。**正确：** 标记为随真空/体积变化的技术结果。
- **错误：** 为让检查通过而创建空 `WAVEDER` 或手改验证报告。**正确：** 保留失败证据并修复真实计算问题。

## 边界例

| 情况 | 期望行为 |
|---|---|
| 实际 KPOINTS 为严格 `1×1×1 Gamma` 且配置了 `vasp_gamma_bin` | 可自动选择 `vasp_gam`；其他网格必须用 `vasp_std` |
| 一个或两个长晶格方向只有 1 个 K 点 | 只标为 2D/1D 候选；没有 `allow_nonbulk_supercell_optics: true` 时暂停 |
| 基态估计带隙小于等于阈值 | 标为 `metal-or-semimetal` 并要求显式金属策略 |
| `energy_eV=0` | 波长写为空/NaN，不能除以零，也不能删除该能量点来伪装完整性 |
| 用户 INCAR 含 DFT+U、磁性或 SOC | 在 `preserve-user` 策略下列出继承项；冲突时暂停，不静默覆盖 |
| `NBANDS` 不足以覆盖目标光子能量 | 结果仅作初步演示；正式结论前增加空带并做收敛测试 |

## 对外发送与公共仓库脱敏

默认只允许在本机/服务器内读取。调用 MatCreator 的外部 API、其他云模型或上传公共仓库前，先向用户说明目的地和文件范围并取得明确授权。

未经逐项授权，不得对外发送或提交：

- `POTCAR`、许可证文件和 API 密钥；
- `WAVECAR`、`CHGCAR`、`OUTCAR`、`vasprun.xml`、`EIGENVAL` 等完整计算文件；
- 包含用户名、服务器名、绝对私有路径或未公开结构坐标的文件。

优先只发送脱敏摘要：结构/电子类别、参数表、文件是否存在、大小、校验状态、CSV 列名和数值范围。摘要中的 `/home/<用户名>/...` 替换为 `<WORKSPACE>/...`，主机名替换为 `<HOST>`，不得包含 API key。公共仓库只放 Skill 源码、无许可证限制的演示输入、脱敏测试报告和不含 POTCAR 的复现说明。

如果用户明确授权发送某几个文件，该授权只覆盖指定目的地和指定文件；不能自动扩展到其他材料、其他结果目录或完整工作区。
