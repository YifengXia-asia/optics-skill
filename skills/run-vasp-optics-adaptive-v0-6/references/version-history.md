# 版本记录

## v0.6

- 将技能名改为动作导向的 `run-vasp-optics-adaptive-v0-6`，保留 v0.5 作为回退版本。
- 新增只读 `scripts/preflight.py`，在分类前检查 Python 包、平台、Bash/GNU timeout、MPI、VASP、oneAPI、输入文件和波长窗口。
- 将波长换算常数、绘图窗口和验证文件名从代码固定值改为 `postprocess` 配置项。
- 增加配置字段类型/约束表、Windows/WSL/macOS 支持矩阵、预检失败处理、反例和禁止伪造结果的停止条件。
- 统一 CSV canonical 字段与 PNG 显示别名，减少 `alpha`/`alpha_cm-1`、`epsilon1`/`eps1` 混用。
- 追加 NBANDS、响应类型、MPI 核数和波长边界的预检，并为每类失败提供诊断命令和重跑规则。
- 增加可执行边界测试表和公共仓库、伪造结果、越权清理等拒绝模板。

## v0.5

- 补充 POSCAR/POTCAR/KPOINTS、config、VASP 产物和 CSV/PNG 的精确契约。
- 统一 `eps1/eps2/n/k/alpha_cm-1/reflectivity` 术语，并说明它们的来源和物理含义。
- 为 inspect/check/prepare/run/extract/plot/validate 增加可读的成功/失败状态码和停止处理。
- 增加缺文件、确认闸门、重复输出目录、非体相/金属/磁性/SOC 候选等正反例。
- 明确 Linux/Unix 运行边界以及 Python 后处理依赖；保留 v0.4 供回退。

## v0.4

首次按输入体系分类，不使用材料名称作为参数分支；增加 KPOINTS/POTCAR 顺序检查、能量域和波长域后处理及只读验证。
