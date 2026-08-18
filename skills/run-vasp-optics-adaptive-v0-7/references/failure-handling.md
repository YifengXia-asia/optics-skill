# 失败处理和停止条件

本技能采用“失败即停止、修复后重跑”的原则。不要用空文件、其他材料结果或手工改写的状态码绕过检查。

| 状态码/现象 | 典型原因 | 处理 |
|---|---|---|
| `PREFLIGHT=FAIL` | Python 包、bash/timeout、MPI、VASP、oneAPI 路径缺失或 MPI 厂商不匹配；平台不支持；输入文件为空；数值参数非法 | 检查 Python、`mpirun --version`、`ldd vasp_std` 和 oneAPI 环境；Intel MPI 链接的 VASP 必须用 Intel MPI 启动器。修复后重跑预检 |
| `INPUT=INVALID` | 缺 POSCAR/POTCAR/KPOINTS、文件不可解析、POSCAR/POTCAR 顺序或块数不一致 | 回到输入目录，补齐真实文件并重新 `--inspect` |
| `CHECK=FAIL` | 输出目录已存在、确认闸门仍为 false、ENCUT 低于 ENMAX、显式 K 点不一致 | 不运行 VASP；审阅建议、换新输出目录或修正配置 |
| `PREPARE=FAIL` | 同上，或无法复制输入 | 不删除原始数据；解决路径/权限/配置后重试 |
| `RUN=PAUSED` | 基态已完成但电子分类、金属模式或非体相解释尚未确认 | 读取 `system_classification.json`，向用户解释后只修改 config，再运行 `--stage loptics` |
| `CLASSIFY=FAIL` | 基态 vasprun.xml 缺本征值、XML 不完整或阈值非法 | 检查基态是否正常结束；不要按材料名称手工写分类 |
| `RUN=FAIL` | oneAPI/MPI/VASP 不可用、VASP 非零退出、缺 OUTCAR/WAVECAR/CHGCAR/WAVEDER、OUTCAR 没有 dielectric/timing | 先执行 `tail -n 80 00_DFT/DFT.stdout` 和 `tail -n 80 01_LOPTICS/LOPTICS.stdout`，再检查 `grep -n "General timing\|DIELECTRIC FUNCTION" OUTCAR`；修复环境或物理输入后使用新 output_dir 重跑 |
| `ALGO=Exact`/ScaLAPACK 段错误 | 小体系在多核精确对角化路径不稳定，或 MPI/NCORE 组合不合适 | 先确认 MPI 厂商匹配；保留失败目录。对极小验证单元可在新目录用同一 Intel MPI 的单核复现，生产体系再系统测试 NCORE/KPAR/核数 |
| `EXTRACT` 依赖错误 | Python 环境缺 PyYAML、NumPy 或 matplotlib，或 vasprun.xml 无所选响应 | 激活正确环境，检查 `parameters.response`，不要伪造 CSV |
| `WAVELENGTH_POSTPROCESS` 错误 | 能量 CSV 不存在或缺必要列 | 先成功完成 `extract.py`，再运行 `plot.py` |
| `VALIDATION=FAIL` | 文件不完整、CSV 非有限值/非单调、R 超界、图缺失或响应类型不匹配 | 修复上游步骤并重新生成，不修改验证结果掩盖失败 |

每次失败都按同一规则处理：保存完整错误行 → 执行表中诊断命令 → 只修改输入/配置或环境 → 使用新的输出目录重跑 → 重新验证。禁止直接编辑 OUTCAR、CSV 或验证报告来制造 PASS。

预检命令示例：

```bash
python scripts/preflight.py --config config.yaml
# Windows 只做后处理依赖检查：
python scripts/preflight.py --config config.yaml --postprocess-only
```

若 `PREFLIGHT=PASS` 但后续仍失败，以失败步骤的状态码为准；不要因为预检通过就跳过 `--inspect`、`--check` 或 `validate.py`。

若体系被分类为 metal/semimetal、磁性候选、SOC 候选、slab/2D、wire/1D 或 molecule 候选，分类本身不是报错；它是“需要单独确认近似”的暂停条件。只有用户明确接受相应近似，且输入参数已经写入配置，才可继续。
