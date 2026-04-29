# AICheck

[![AICheck Analysis](https://github.com/handsome-Druid/AICheck/actions/workflows/aicheck-analysis.yml/badge.svg)](https://github.com/handsome-Druid/AICheck/actions/workflows/aicheck-analysis.yml)

![AICheck 界面截图](assets/screenshot.png)

**AICheck** 是一个用于自动化验证 vLLM 模型部署正确性的桌面工具。  
它能够批量连接多个模型服务端点，检查每个端口的模型列表是否与预期一致，并实时反馈连接状态、响应时间、多余/缺失模型等诊断信息。所有结果可导出为 CSV 文件，便于集成到质量保障流程中。

---

## ✨ 特性

- **批量检测** 同时检测上千个 vLLM 服务端点，识别模型异常。
- **详细报告** 每个端点的状态（成功/失败/超时）、实际模型、多余模型、缺失模型、响应时间一目了然。
- **GUI 与命令行双模式** 提供 PySide6 图形界面，也支持 `--nogui` 无头模式，适合 CI 集成。
- **历史数据导入** 支持读取已有的 CSV / XLSX 结果文件进行对比分析。
- **高性能** 基于 `asyncio` + `httpx` 异步并发，检测速度快。
- **跨平台** 源码跨平台，同时提供 Windows 单文件 EXE（通过 Nuitka + UPX 压缩打包）。
- **完善的 CI/CD** 集成 Pyright、Mypy strict、SonarCloud、Sourcery、100% 测试覆盖率、pyinstrument 性能监控等质量门禁。

---

## 🚀 快速开始

### 环境要求

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) (推荐) 或 pip

### 安装

```bash
git clone https://github.com/handsome-Druid/AICheck.git
cd AICheck
uv sync
```

### 运行 GUI

```bash
uv run python src/main.py
```

### 命令行模式（批量检测）

```bash
uv run python src/main.py --nogui --nopause
```

程序将从 `settings.json` 读取 vLLM 端点列表并逐一检测，结果自动保存为 CSV。

---

## ⚙️ 配置

复制 `settings.json.example` 为 `settings.json`，按需修改：

```json
{
  "vllm_servers": [
    {"ip": "127.0.0.1", "port": 30000, "model_id": "model-0000", "container_name": "container-0000"}
  ],
  "timeout": 3.0,
  "output_dir": "output/results"
}
```

---

## 🧪 开发与质量

本项目通过严格的 CI 流水线保证代码质量。以下是最新一轮的运行结果摘要：

| 检查项 | 工具 | 状态 / 结果 |
|--------|------|-------------|
| 类型检查 | Pyright, Mypy `--strict` | ✅ 0 errors / 0 warnings |
| 静态分析 | SonarCloud | 0 Bugs, 0 Vulnerabilities, 0 Code Smells |
| 代码审查 | Sourcery | 0 issues |
| 单元测试 & 覆盖率 | Coverage.py | **100%** 覆盖（966 语句，76 测试全部通过） |
| 性能分析 | pyinstrument | 集成测试通过（1000 端点检测） |
| 代码统计 | scc | 34 Python 文件, 3,271 逻辑行, 405 复杂度 |
| UI 生成校验 | pyside6-uic | 自动生成且无 diff |

想要在本地运行全部检查：

```bash
uv run pyright ./
uv run mypy --strict ./
uv run python -m coverage run --source=src -m unittest discover -s tests && uv run python -m coverage report -m
```

---

## 📦 构建与发布

CI 流水线会自动使用 Nuitka 构建 Windows 单文件 EXE，并通过 UPX 压缩体积。  
每当推送新的标签（如 `v1.1.2`）时，会自动创建 GitHub Release 并上传构建产物。

你可以从 [Releases 页面](https://github.com/handsome-Druid/AICheck/releases/latest) 下载最新的 `main.exe`。

若需本地构建：

```bash
uv run python -OO -m nuitka \
  --onefile --standalone --windows-console-mode=disable \
  --enable-plugin=pyside6 --plugin-enable=upx \
  src/main.py
```

构建产物将输出到 `output/nuitka/main.exe`。

---

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源，欢迎贡献。

---

## 🤝 贡献

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

所有 PR 必须通过 CI 流水线（类型检查、测试、SonarCloud 等）后方可合入。