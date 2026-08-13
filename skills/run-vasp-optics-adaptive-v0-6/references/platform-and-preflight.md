# 平台和预检说明

## 推荐运行环境

完整 DFT→LOPTICS 流程优先放在 Linux 集群上。`run.py` 使用 Bash 的 `source`、GNU `timeout` 和 MPI 启动器；这些不是原生 Windows PowerShell 的命令。WSL2 可以作为 Linux 环境，但必须在 WSL 内安装/挂载 VASP、MPI 和 Python 包。

macOS 可以运行 `config_loader.py`、`extract.py`、`plot.py`、`validate.py`；若要运行 VASP，还需自行提供可执行 VASP、MPI 和 GNU `timeout`。原生 Windows 只建议做 `--postprocess-only` 预检和后处理。

## 预检顺序

1. 确认当前 Python 是目标环境中的解释器：`python -c "import sys; print(sys.executable)"`。
2. 执行 `python scripts/preflight.py --config config.yaml`。
3. 看到 `PREFLIGHT=PASS` 后再执行 `config_loader.py --inspect`。
4. 若只做已有 `vasprun.xml` 的提取和绘图，在 Windows 可使用 `--postprocess-only`，但仍需 NumPy、pandas、matplotlib、PyYAML。

预检是只读的，不创建运行目录、不调用 VASP、不修改输入。`oneapi_setup` 为空表示用户已在当前 shell 加载 oneAPI；尖括号占位符表示配置未完成，必须停止。
