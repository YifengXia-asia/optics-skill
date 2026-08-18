# v0.7 三类材料端到端测试矩阵

| 代号 | 结构类型目标 | 实际测试体系 | 电子分类来源 | 预期解释 |
|---|---|---|---|---|
| bulk-3d | bulk-3d-candidate | 两原子三维二元晶体输入 | 基态 vasprun.xml | 可输出三维体光学常数 |
| slab-2d | slab-or-2d-candidate | 含真空层的两原子碳薄层 | 基态 vasprun.xml | 技术结果可复现，但随真空体积变化 |
| wire-1d | wire-or-1d-candidate | 两个真空方向的一维周期碳链；6 Å 横向晶格仅用于流程冒烟测试，不代表真空已收敛 | 基态 vasprun.xml | 技术结果可复现，但随横向真空面积变化，正式研究必须做真空收敛 |

每个案例执行 `preflight -> inspect -> check -> prepare -> run -> extract -> plot -> validate`，并保存所有状态码。测试目录与用户原始 SiC 目录分离。

并行策略：三维小体相使用 4 个 Intel MPI 进程；二维和一维验证单元使用 1 个 Intel MPI 进程，避免 VASP 6.3.2 在小体系 `ALGO=Exact` 的 ScaLAPACK 并行段错误。该选择只影响测试执行稳定性，不作为材料名称规则。
