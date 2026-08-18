# 版本记录

## v0.7

2026-08-18 修订：补充依赖获得方式、术语表、正例/反例/边界例、对外发送和公共仓库的脱敏规则；将结构分类、ENCUT 取整、K 点对照密度和 NBANDS 余量阈值外置到配置，默认值保持与实跑版本一致。

- 保留用户实际 KPOINTS，不再把几何推荐网格当作有效输入。
- 支持从可选 INCAR 继承用户泛函、DFT+U、磁性和 SOC 相关标签。
- 将流程改为两次确认：输入/结构确认后运行 DFT，再从实际本征值确认电子类型后运行 LOPTICS。
- 新增 bulk、2D/slab、1D/wire、isolated/molecule 结构候选和超胞依赖元数据。
- 新增 metal/semimetal 的 stop、interband-only、Drude 三分支；Drude 宽度必须由用户提供。
- DFT 与 LOPTICS 使用兼容 NBANDS；新增 `system_classification.json`。
- 后处理增加损失函数、光学电导率及对应能量/波长图。
- 预检增加 MPI 厂商匹配检查，阻止 Open MPI 启动器与 Intel MPI 链接 VASP 混用。
- 对严格 1×1×1 Gamma 输入支持按 KPOINTS 自动选择已配置的 `vasp_gam`。

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
