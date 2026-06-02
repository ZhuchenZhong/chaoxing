# ZhuchenZhong/chaoxing

超星学习通自动化学习工具，当前分支重点改造为 uv 管理、Rich 进度输出和用户目录配置。

本仓库是 `Samueli924/chaoxing` 的 fork，保留 GPL-3.0 许可和上游来源说明。

<p align="center">
  <a href="https://github.com/ZhuchenZhong/chaoxing">
    <img src="https://img.shields.io/github/stars/ZhuchenZhong/chaoxing" alt="Github Stars" />
  </a>
  <a href="https://github.com/ZhuchenZhong/chaoxing">
    <img src="https://img.shields.io/github/forks/ZhuchenZhong/chaoxing" alt="Github Forks" />
  </a>
  <a href="https://github.com/ZhuchenZhong/chaoxing">
    <img src="https://img.shields.io/github/languages/code-size/ZhuchenZhong/chaoxing" alt="Code-size" />
  </a>
</p>

## 主要变化

- 使用 `uv` 管理依赖和锁文件，依赖以 `pyproject.toml`/`uv.lock` 为准。
- 默认命令 `chaoxing` 使用原来的交互式 CLI 流程，并保留 Rich 多行进度显示。
- 显式传入 `-c/--config` 时读取 `config.ini`，默认推荐位置是 `~/.chaoxing/config.ini`。
- Textual TUI 暂时保留为备用入口，不作为默认启动流程。
- 登录 Cookie、运行日志等运行态文件默认放入 `~/.chaoxing/`，可用 `CHAOXING_HOME` 改写目录。
- 刷课进度使用 Rich 多行进度条，底层 trace/debug 日志写入 `~/.chaoxing/logs/chaoxing.log`。

## 安装与运行

```bash
git clone https://github.com/ZhuchenZhong/chaoxing
cd chaoxing
uv sync
```

启动原 CLI（Rich 输出）：

```bash
uv run chaoxing
```

默认 CLI 无 `-c` 时会按原流程交互输入账号密码和课程列表。按配置文件非交互运行：

```bash
uv run chaoxing run -c ~/.chaoxing/config.ini
```

备用 TUI 入口：

```bash
uv run chaoxing tui
```

兼容旧入口：

```bash
uv run python main.py -c ~/.chaoxing/config.ini
```

## 配置文件

默认 CLI 不会自动生成或读取 `~/.chaoxing/config.ini`；显式使用 `-c ~/.chaoxing/config.ini` 或备用 TUI 时，会从 `config_template.ini` 生成并使用同一个 `config.ini`。

账号策略：

- 默认保存账号和 Cookie。
- 备用 TUI 中只有勾选“记住密码并写入 config.ini”时才保存密码。
- 不勾选时，备用 TUI 可以临时使用本次输入的密码，但写回配置会清空 `password` 字段。

常用配置段：

- `[common]`：账号、Cookie 登录、课程 ID、倍速、并发、关闭章节处理策略。
- `[tiku]`：题库 provider、token、是否提交、覆盖率、查询延迟。
- `[notification]`：ServerChan、Qmsg、Bark、Telegram 等通知配置。

## Docker

Docker 默认把运行态放在 `/config/.chaoxing`，并使用 `/config/config.ini`：

```bash
docker build -t chaoxing .
docker run -it -v /本地路径:/config chaoxing
```

## 开发验证

```bash
uv lock
uv sync
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q api main.py chaoxing_cli.py app.py tests
uv run chaoxing --help
uv run chaoxing run --help
```

## 上游同步

推荐本地 remote：

```bash
git remote set-url origin https://github.com/ZhuchenZhong/chaoxing.git
git remote add upstream https://github.com/Samueli924/chaoxing.git
git fetch origin
git fetch upstream
```

## 免责声明

- 本代码遵循 GPL-3.0 License。基于本代码的修改和衍生程序必须继续遵守 GPL-3.0。
- 本代码仅用于学习讨论，禁止用于盈利或违法用途。
- 他人或组织使用本代码造成的任何后果与维护者无关。
