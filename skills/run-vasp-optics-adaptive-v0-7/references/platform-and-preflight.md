# 平台和预检说明

## 推荐运行环境

完整 DFT→LOPTICS 流程优先放在 Linux 集群上。`run.py` 使用 Bash 的 `source`、GNU `timeout` 和 MPI 启动器；这些不是原生 Windows PowerShell 的命令。WSL2 可以作为 Linux 环境，但必须在 WSL 内安装/挂载 VASP、MPI 和 Python 包。

macOS 可以运行 `config_loader.py`、`extract.py`、`plot.py`、`validate.py`；若要运行 VASP，还需自行提供可执行 VASP、MPI 和 GNU `timeout`。原生 Windows 只建议做 `--postprocess-only` 预检和后处理。

## 依赖如何获得

| 依赖 | 获得方式 | 本技能是否自动安装 |
|---|---|---|
| VASP 和 POTCAR | 由拥有有效 VASP 许可证的用户或集群管理员从 VASP 官方渠道取得、编译并部署 | 否；不得下载、复制给无权用户或伪造 |
| Intel oneAPI / Intel MPI / MKL | 使用集群 module，或由管理员按 Intel oneAPI 官方安装说明部署 | 否；只读取 `oneapi_setup` 并检查可执行文件和链接库 |
| 其他 MPI | 使用系统包或集群 module；必须与 `ldd vasp_std` 显示的 MPI 实现一致 | 否 |
| Bash 与 GNU `timeout` | Linux 通常由系统提供；缺失时由管理员安装 GNU coreutils | 否 |
| Python 3.10+ | conda、venv 或集群 Python module | 否 |
| PyYAML、NumPy、pandas、matplotlib、lxml | 在用户自己的 Python 环境中安装，例如 `conda install pyyaml numpy pandas matplotlib lxml` | 否；预检只报告缺项 |

不能取得合法 VASP/POTCAR、没有匹配的 MPI，或无权安装依赖时必须停止并联系管理员；不能让 Skill 绕过许可证或集群策略。

## 预检顺序

1. 确认当前 Python 是目标环境中的解释器：`python -c "import sys; print(sys.executable)"`。
2. 执行 `python scripts/preflight.py --config config.yaml`。
3. 看到 `PREFLIGHT=PASS` 后再执行 `config_loader.py --inspect`。
4. 若只做已有 `vasprun.xml` 的提取和绘图，在 Windows 可使用 `--postprocess-only`，但仍需 NumPy、pandas、matplotlib、PyYAML、lxml。

预检是只读的，不创建运行目录、不调用 VASP、不修改输入。`oneapi_setup` 为空表示用户已在当前 shell 加载 oneAPI；尖括号占位符表示配置未完成，必须停止。

预检比较 MPI 厂商：`mpirun --version` 必须与 `ldd vasp_std` 显示的 MPI 运行库一致。若 VASP 链接 `/opt/intel/oneapi/mpi/.../libmpi.so.12`，应使用 oneAPI 的 `mpi/latest/bin/mpirun`，不能使用 Open MPI 的 `/usr/bin/mpirun`。
