# v0.7 三类型服务器验证报告

验证日期：2026-08-18

服务器：`<HOST>`（通过用户配置的 SSH 别名连接）

VASP：6.3.2，Intel oneAPI / Intel MPI / MKL 版本

Skill：`run-vasp-optics-adaptive-v0-7`

## 结论

Skill 没有按 SiC、石墨烯或碳链名称选择参数，而是按输入晶格/KPOINTS 判断结构候选，再按基态 `vasprun.xml` 的实际本征值和占据数判断电子候选。三组正式用例的 DFT、LOPTICS、提取、绘图和只读验证均通过。

| 用例标签 | 结构分类 | 电子分类 | 估计带隙 | 解释范围 | 最终状态 |
|---|---|---|---:|---|---|
| bulk-3d | `bulk-3d-candidate` | `semiconductor` | 1.342 eV | 三维体相内禀光学常数候选 | `VALIDATION=PASS` |
| slab-2d | `slab-or-2d-candidate` | `metal-or-semimetal` | 0.0 eV | 随真空体积变化的超胞结果 | `VALIDATION=PASS` |
| wire-1d | `wire-or-1d-candidate` | `metal-or-semimetal` | 0.0 eV | 随横向超胞面积变化的超胞结果 | `VALIDATION=PASS` |

## 完整性证据

每组均满足：

- `OUTCAR`、`vasprun.xml`、`WAVECAR`、`WAVEDER` 非空；
- OUTCAR 同时包含频率相关介电函数实部、虚部和 `General timing and accounting`；
- 能量域 CSV 为 2000 行；波长域 CSV 为 1999 行，少的一行对应零能量点，避免除以零；
- 19 张 PNG 完整，覆盖 `eps1/eps2/n/k/alpha_cm-1/reflectivity/loss_function/sigma1_S_m` 的能量/波长图和指定波长窗口图；
- `density-density` 和 `current-current` 响应块均被发现，按配置读取 `density-density`；
- 最终 `VALIDATION=PASS`，且 2D/1D 元数据中的 `intrinsic_bulk_optics=false`。

关键文件大小：

| 用例 | OUTCAR | vasprun.xml | WAVECAR | WAVEDER | MPI |
|---|---:|---:|---:|---:|---|
| bulk-3d | 132234 B | 1060025 B | 1780800 B | 98432 B | Intel MPI，4 核 |
| slab-2d | 118858 B | 1054662 B | 6151488 B | 92288 B | Intel MPI，1 核 |
| wire-1d | 108281 B | 1045243 B | 2158976 B | 23168 B | Intel MPI，1 核 |

## 发现并保留的问题

1. `/usr/bin/mpirun` 是 Open MPI，而 VASP 链接 Intel MPI。旧的错误启动结果已经归档；最终配置改用 `/opt/intel/oneapi/mpi/latest/bin/mpirun`。最终 Skill 的预检会直接阻止该不匹配。
2. 2D 用例在 4 核 `ALGO=Exact` 阶段触发本机 VASP/ScaLAPACK 段错误，改为 1 个 Intel MPI 进程后完成。这是当前 VASP 构建/并行组合的限制，不是物理参数已经收敛的证明。
3. 大真空孤立 C2 测试和 10 Å 横向一维测试在当前 VASP 构建上发生段错误，失败目录被保留。正式第三类改为 6 Å 横向一维周期冒烟测试后跑通；6 Å 只验证流程，不代表真空层已收敛。
4. bulk-3d 的 1.342 eV 是当前输入、泛函、K 点和空带设置下的工作流分类结果，不能直接当作实验带隙或高精度预测。

## 自动测试与静态评分

- 本地 6 项自动测试通过：3D/2D/1D/孤立候选分类、用户 KPOINTS 保留、用户 INCAR 优先、电子类别路由、阈值可配置、完整已有 DFT 只读复用、不完整已有 DFT 拒绝。
- Skill Creator `quick_validate.py`：通过。
- Skill-eval v3.1：`98.5/100（卓越）`。
- Skill-eval 报告：`llm_errors={}`、缺失引用为空、frontmatter 警告为空。
- 唯一非 A 项为“恶意/资源滥用拒绝边界”B；科学和运行安全边界已经明确，但没有穷举通用恶意场景。

## MatCreator 测试

安全发现测试在不含 VASP 数据的空工作区完成：

- API 调用成功；
- MatCreator 能识别并加载 `run-vasp-optics-adaptive-v0-7`；
- 能正确解释三个必需输入、两次分类、两次人工确认、3D/2D/1D 解释差异和命令顺序；
- 没有运行 VASP，也没有读取 POTCAR/OUTCAR/vasprun.xml/WAVECAR/WAVEDER。

但事件审计发现 MatCreator 为定位 Skill 执行了对 `<HOME>` 的广泛文件名搜索。它只读取了目标 Skill 文档，没有读取 VASP 结果；仍说明 MatCreator 的工具边界控制不够精细。对三组完整结果做 API 验收前，必须得到用户针对这些结果文件和 DeepSeek 目的地的明确授权。

不点名 Skill 的自然语言测试“SiC 基态 DFT 已完成，继续算吸收率”没有可靠选中 v0.7，而是检索到旧 v0.6 和早期 SiC 版本，最终回答也未正常交付。按用户约束，后续没有修改 MatCreator 源码、配置或搜索逻辑；只在 v0.7 Skill 的 frontmatter/body 中加入普通用户触发语义和隐式调用声明。因此 Skill 文件已具备正确触发描述，但 MatCreator 是否及时重建其外部索引不由本 Skill 控制。

## 已有 DFT 只读复用测试

以已完成的 bulk-3d 基态目录为源，设置 `run.existing_dft_dir` 后执行 `--inspect → prepare.py → run.py --stage dft`：

- `INSPECT=OK;NO_FILES_CREATED=true`；
- `DFT_SOURCE=REUSED_COPY;SOURCE_MODIFIED=false`；
- 未启动 VASP；
- 从复制的 `vasprun.xml` 得到 `semiconductor`、`1.342 eV`，随后停在第二确认门；
- 源目录 `OUTCAR/vasprun.xml/WAVECAR/CHGCAR` 前后 SHA-256 完全一致。
