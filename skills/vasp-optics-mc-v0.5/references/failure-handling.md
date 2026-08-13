# 失败处理和停止条件

本技能采用“失败即停止、修复后重跑”的原则。不要用空文件、其他材料结果或手工改写的状态码绕过检查。

| 状态码/现象 | 典型原因 | 处理 |
|---|---|---|
| `INPUT=INVALID` | 缺 POSCAR/POTCAR/KPOINTS、文件不可解析、POSCAR/POTCAR 顺序或块数不一致 | 回到输入目录，补齐真实文件并重新 `--inspect` |
| `CHECK=FAIL` | 输出目录已存在、确认闸门仍为 false、ENCUT 低于 ENMAX、显式 K 点不一致 | 不运行 VASP；审阅建议、换新输出目录或修正配置 |
| `PREPARE=FAIL` | 同上，或无法复制输入 | 不删除原始数据；解决路径/权限/配置后重试 |
| `RUN=FAIL` | oneAPI/MPI/VASP 不可用、VASP 非零退出、缺 OUTCAR/WAVECAR/CHGCAR/WAVEDER、OUTCAR 没有 dielectric/timing | 查看 `DFT.stdout`/`LOPTICS.stdout` 和 OUTCAR；先修复环境或物理输入 |
| `EXTRACT` 依赖错误 | Python 环境缺 PyYAML、NumPy 或 matplotlib，或 vasprun.xml 无所选响应 | 激活正确环境，检查 `parameters.response`，不要伪造 CSV |
| `WAVELENGTH_POSTPROCESS` 错误 | 能量 CSV 不存在或缺必要列 | 先成功完成 `extract.py`，再运行 `plot.py` |
| `VALIDATION=FAIL` | 文件不完整、CSV 非有限值/非单调、R 超界、图缺失或响应类型不匹配 | 修复上游步骤并重新生成，不修改验证结果掩盖失败 |

若体系被分类为 metal、磁性候选、SOC 候选、slab/2D 或 molecule 候选，分类本身不是报错；它是“需要单独确认近似”的停止条件。只有用户明确接受相应近似，且输入参数已经写入配置，才可继续。
