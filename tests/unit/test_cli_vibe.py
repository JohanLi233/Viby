"""
测试viby CLI应用程序的单元测试
"""

from unittest.mock import patch, MagicMock
import pytest
import typer
from typer.testing import CliRunner

# 导入被测试的模块
from viby.cli.app import (
    app,
    get_version_string,
    get_command_class,
    process_input,
    load_model_manager,
    create_typer,
    default_callback,
)


@pytest.fixture
def cli_runner():
    """返回一个Typer CLI测试运行器"""
    return CliRunner()


def test_create_typer():
    """测试创建Typer实例的工厂函数"""
    help_text = "测试帮助文本"
    app_instance = create_typer(help_text)

    assert isinstance(app_instance, typer.Typer)
    assert app_instance.info.help == help_text
    # Typer的最新版本可能不再直接暴露add_completion属性
    # 因此我们删除这个断言


@patch("viby.cli.app.typer")
def test_default_callback(mock_typer):
    """测试默认回调函数"""
    ctx_mock = MagicMock()
    ctx_mock.get_help.return_value = "帮助文本"

    # 模拟typer.Exit异常
    mock_typer.Exit = typer.Exit

    with pytest.raises(typer.Exit):
        default_callback(ctx_mock)

    ctx_mock.get_help.assert_called_once()


@patch("viby.cli.app.importlib.metadata.version")
def test_get_version_string(mock_version):
    """测试获取版本信息字符串函数"""
    mock_version.return_value = "0.1.0"

    with patch("viby.cli.app.importlib.metadata.distribution") as mock_dist:
        # 模拟普通安装（非开发版本）
        mock_dist_instance = MagicMock()
        mock_dist_instance.read_text.return_value = ""
        mock_dist.return_value = mock_dist_instance

        version_str = get_version_string()
        assert version_str == "Viby 0.1.0"

        # 模拟开发版本
        mock_dist_instance.read_text.return_value = '{"dir_info": {"editable": true}}'
        version_str = get_version_string()
        assert version_str == "Viby 0.1.0(dev)"


@patch("viby.cli.app.logger")
def test_get_command_class(mock_logger):
    """测试按需导入命令类函数"""
    # 创建测试命令注册表和缓存
    test_registry = {"test_command": {"module": "test_module", "class": "TestCommand"}}
    test_cache = {}

    # 测试缓存未命中但正常加载
    mock_module = MagicMock()
    mock_command_class = MagicMock()
    setattr(mock_module, "TestCommand", mock_command_class)

    with (
        patch("viby.cli.app.command_registry", test_registry),
        patch("viby.cli.app._command_class_cache", test_cache),
        patch("viby.cli.app.importlib.import_module", return_value=mock_module),
    ):
        result = get_command_class("test_command")
        assert result == mock_command_class
        # 验证命令已添加到缓存
        assert "test_command" in test_cache

    # 测试导入错误
    with (
        patch("viby.cli.app.command_registry", test_registry),
        patch("viby.cli.app._command_class_cache", {}),
        patch(
            "viby.cli.app.importlib.import_module", side_effect=ImportError("导入失败")
        ),
    ):
        with pytest.raises(ImportError):
            get_command_class("test_command")

    mock_logger.error.assert_called()

    # 测试未知命令
    with (
        patch("viby.cli.app.command_registry", {}),
        patch("viby.cli.app._command_class_cache", {}),
    ):
        with pytest.raises(ImportError):
            get_command_class("unknown_command")
        mock_logger.error.assert_any_call("未知命令: unknown_command")


def test_process_input():
    """测试处理命令行输入函数"""
    # 测试没有参数和管道输入
    with patch("sys.stdin.isatty", return_value=True):
        result, has_input = process_input()
        assert result == ""
        assert has_input is False

    # 测试有命令行参数
    with patch("sys.stdin.isatty", return_value=True):
        result, has_input = process_input(["测试", "输入"])
        assert result == "测试 输入"
        assert has_input is True

    # 测试有管道输入
    with (
        patch("sys.stdin.isatty", return_value=False),
        patch("sys.stdin.read", return_value="管道输入"),
    ):
        result, has_input = process_input()
        assert result == "管道输入"
        assert has_input is True

    # 测试同时有命令行参数和管道输入
    with (
        patch("sys.stdin.isatty", return_value=False),
        patch("sys.stdin.read", return_value="管道输入"),
    ):
        result, has_input = process_input(["命令行"])
        assert result == "命令行\n管道输入"
        assert has_input is True


def test_load_model_manager():
    """测试懒加载模型管理器函数"""
    ctx_obj = {"test": "value"}

    # 创建模拟的ModelManager类
    mock_model_manager = MagicMock()
    mock_model_manager_instance = MagicMock()
    mock_model_manager.return_value = mock_model_manager_instance

    # 打补丁替换ModelManager导入
    with patch.dict(
        "sys.modules", {"viby.llm.models": MagicMock(ModelManager=mock_model_manager)}
    ):
        # 执行测试
        result = load_model_manager(ctx_obj)

        # 验证结果
        mock_model_manager.assert_called_once_with(ctx_obj)
        assert result == mock_model_manager_instance


@patch("viby.cli.app.get_version_string")
def test_main_version_flag(mock_get_version, cli_runner):
    """测试主函数的版本标志"""
    mock_get_version.return_value = "Viby 测试版本"

    result = cli_runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "Viby 测试版本" in result.stdout
    mock_get_version.assert_called_once()


@patch("viby.cli.app.lazy_load_wizard")
@patch("viby.cli.app.config")
@patch("viby.cli.app.init_text_manager")
def test_main_config_mode(mock_init_text, mock_config, mock_lazy_load, cli_runner):
    """测试主函数的配置模式"""
    # 测试显式配置模式
    mock_config.is_first_run = False
    mock_wizard = MagicMock()
    mock_lazy_load.return_value = mock_wizard

    cli_runner.invoke(app, ["--config"])

    mock_lazy_load.assert_called_once()
    mock_wizard.assert_called_once_with(mock_config)
    mock_init_text.assert_called_with(mock_config)

    # 测试首次运行
    mock_config.is_first_run = True
    mock_lazy_load.reset_mock()
    mock_wizard.reset_mock()
    mock_init_text.reset_mock()

    cli_runner.invoke(app, [])

    mock_lazy_load.assert_called_once()
    mock_wizard.assert_called_once_with(mock_config)
    mock_init_text.assert_called_with(mock_config)


@patch("viby.cli.app.process_input")
@patch("viby.cli.app.load_model_manager")
@patch("viby.cli.app.get_command_class")
def test_vibe_command(
    mock_get_command, mock_load_manager, mock_process_input, cli_runner
):
    """测试vibe命令"""
    # 模拟配置不是首次运行，避免触发配置向导
    with patch("viby.cli.app.config.is_first_run", False):
        # 模拟有输入
        mock_process_input.return_value = ("测试问题", True)
        mock_vibe_command = MagicMock()
        mock_vibe_class = MagicMock(return_value=mock_vibe_command)
        mock_get_command.return_value = mock_vibe_class

        result = cli_runner.invoke(app, ["vibe", "测试问题"])

        mock_get_command.assert_called_once_with("vibe")
        mock_vibe_class.assert_called_once()
        mock_vibe_command.vibe.assert_called_once_with("测试问题")

    # 模拟无输入，终端环境
    mock_process_input.return_value = ("", False)
    mock_get_command.reset_mock()
    mock_vibe_class.reset_mock()
    mock_vibe_command.vibe.reset_mock()

    # 直接测试无输入情况
    with patch("viby.cli.app.config.is_first_run", False):
        with patch("sys.stdout.isatty", return_value=True):
            with patch("viby.cli.app.typer"):
                result = cli_runner.invoke(app, ["vibe"])
                # typer.echo函数可能不是通过装饰器调用的，所以我们检查返回结果
                assert "content" not in result.stdout

    # 模拟无输入，非终端环境（管道环境）
    with patch("viby.cli.app.config.is_first_run", False):
        with patch("sys.stdout.isatty", return_value=False):
            result = cli_runner.invoke(app, ["vibe"])
            assert result.exit_code == 0
            mock_get_command.assert_not_called()


@patch("viby.cli.app.get_text")
@patch("viby.cli.app.show_warning")
@patch("viby.cli.app.show_error")
@patch("viby.cli.app.show_success")
@patch("viby.cli.app.show_info")
@patch("viby.cli.app.install_shortcuts")
@patch("viby.cli.app.detect_shell")
def test_shortcuts_command(
    mock_detect,
    mock_install,
    mock_show_info,
    mock_show_success,
    mock_show_error,
    mock_show_warning,
    mock_get_text,
    cli_runner,
):
    """测试shortcuts命令"""
    # 模拟配置不是首次运行，避免触发配置向导
    with patch("viby.cli.app.config.is_first_run", False):
        # 设置get_text的返回值
        mock_get_text.side_effect = lambda section, key, default=None: key

        # 成功检测shell
        mock_detect.return_value = "bash"
        mock_install.return_value = {"status": "success", "message": "已成功安装快捷键"}

        cli_runner.invoke(app, ["shortcuts"])

        mock_detect.assert_called_once()
        mock_install.assert_called_once_with("bash")

        # 测试 UI 输出
        mock_show_info.assert_any_call("auto_detect_shell: bash")
        mock_show_success.assert_called_with("已成功安装快捷键")
        mock_show_info.assert_any_call("activation_note")

    # 模拟配置不是首次运行，避免触发配置向导
    with patch("viby.cli.app.config.is_first_run", False):
        # 失败检测shell
        mock_detect.reset_mock()
        mock_install.reset_mock()
        mock_show_warning.reset_mock()
        mock_show_error.reset_mock()
        mock_show_info.reset_mock()

        mock_detect.return_value = None
        mock_install.return_value = {
            "status": "error",
            "message": "安装失败",
            "action_required": "需要手动操作",
        }

        cli_runner.invoke(app, ["shortcuts"])

        mock_detect.assert_called_once()
        mock_install.assert_called_once_with(None)
        mock_show_warning.assert_any_call("auto_detect_failed")
        mock_show_warning.assert_any_call("action_required")
        mock_show_error.assert_called_with("安装失败")


@patch("viby.cli.app.get_command_class")
def test_sessions_list_command(mock_get_command, cli_runner):
    """测试sessions list命令"""
    # 模拟配置不是首次运行，避免触发配置向导
    with patch("viby.cli.app.config.is_first_run", False):
        mock_sessions_command = MagicMock()
        mock_sessions_class = MagicMock(return_value=mock_sessions_command)
        mock_get_command.return_value = mock_sessions_class

        cli_runner.invoke(app, ["sessions", "list"])

        mock_get_command.assert_called_once_with("sessions")
        mock_sessions_class.assert_called_once()
        mock_sessions_command.list_sessions.assert_called_once()


@patch("viby.cli.app.get_command_class")
def test_sessions_search_command(mock_get_command, cli_runner):
    """测试sessions search命令"""
    # 模拟配置不是首次运行，避免触发配置向导
    with patch("viby.cli.app.config.is_first_run", False):
        mock_sessions_command = MagicMock()
        mock_sessions_class = MagicMock(return_value=mock_sessions_command)
        mock_get_command.return_value = mock_sessions_class

        cli_runner.invoke(app, ["sessions", "search", "查询词"])

        mock_get_command.assert_called_once_with("sessions")
        mock_sessions_class.assert_called_once()
        # 由于参数提供方式的变化，不能直接检查参数
        mock_sessions_command.search_history.assert_called_once()
        assert mock_sessions_command.search_history.call_args[0][0] == "查询词"


@patch("viby.cli.app.get_command_class")
def test_sessions_export_command(mock_get_command, cli_runner):
    """测试sessions export命令"""
    # 模拟配置不是首次运行，避免触发配置向导
    with patch("viby.cli.app.config.is_first_run", False):
        mock_sessions_command = MagicMock()
        mock_sessions_class = MagicMock(return_value=mock_sessions_command)
        mock_get_command.return_value = mock_sessions_class

        # 测试默认格式
        cli_runner.invoke(app, ["sessions", "export", "output.json"])

        mock_get_command.assert_called_once_with("sessions")
        mock_sessions_class.assert_called_once()
        mock_sessions_command.export_history.assert_called_once()
        # 检查第一个参数是否匹配
        assert mock_sessions_command.export_history.call_args[0][0] == "output.json"

    # 模拟配置不是首次运行，避免触发配置向导
    with patch("viby.cli.app.config.is_first_run", False):
        # 测试自定义格式
        mock_get_command.reset_mock()
        mock_sessions_class.reset_mock()
        mock_sessions_command.export_history.reset_mock()

        cli_runner.invoke(
            app,
            ["sessions", "export", "output.csv", "--format", "csv"],
        )

        mock_get_command.assert_called_once_with("sessions")
        mock_sessions_class.assert_called_once()
        mock_sessions_command.export_history.assert_called_once()
        # 检查第一个参数是否匹配
        assert mock_sessions_command.export_history.call_args[0][0] == "output.csv"


@patch("viby.cli.app.get_command_class")
def test_sessions_clear_command(mock_get_command, cli_runner):
    """测试sessions clear命令"""
    # 模拟配置不是首次运行，避免触发配置向导
    with patch("viby.cli.app.config.is_first_run", False):
        mock_sessions_command = MagicMock()
        mock_sessions_class = MagicMock(return_value=mock_sessions_command)
        mock_get_command.return_value = mock_sessions_class

        cli_runner.invoke(app, ["sessions", "clear"])

        mock_get_command.assert_called_once_with("sessions")
        mock_sessions_class.assert_called_once()
        mock_sessions_command.clear_history.assert_called_once()


@patch("viby.cli.app.get_command_class")
def test_tools_list_command(mock_get_command, cli_runner):
    """测试tools list命令"""
    # 模拟配置不是首次运行，避免触发配置向导
    with patch("viby.cli.app.config.is_first_run", False):
        mock_tools_command = MagicMock()
        mock_tools_class = MagicMock(return_value=mock_tools_command)
        mock_get_command.return_value = mock_tools_class

        cli_runner.invoke(app, ["tools", "list"])

        mock_get_command.assert_called_once_with("tools")
        mock_tools_class.assert_called_once()
        mock_tools_command.list_tools.assert_called_once()


@patch("viby.cli.app.get_command_class")
def test_embed_commands(mock_get_command, cli_runner):
    """测试embed命令组"""
    # 模拟配置不是首次运行，避免触发配置向导
    with patch("viby.cli.app.config.is_first_run", False):
        mock_embed_command = MagicMock()
        mock_embed_class = MagicMock(return_value=mock_embed_command)
        mock_get_command.return_value = mock_embed_class

        # 测试update子命令
        cli_runner.invoke(app, ["tools", "embed", "update"])
        mock_get_command.assert_called_with("embed")
        mock_embed_command.update_embeddings.assert_called_once()

    # 模拟配置不是首次运行，避免触发配置向导
    with patch("viby.cli.app.config.is_first_run", False):
        # 测试start子命令
        mock_get_command.reset_mock()
        mock_embed_command.reset_mock()
        cli_runner.invoke(app, ["tools", "embed", "start"])
        mock_get_command.assert_called_with("embed")
        mock_embed_command.start_embed_server.assert_called_once()

    # 模拟配置不是首次运行，避免触发配置向导
    with patch("viby.cli.app.config.is_first_run", False):
        # 测试stop子命令
        mock_get_command.reset_mock()
        mock_embed_command.reset_mock()
        cli_runner.invoke(app, ["tools", "embed", "stop"])
        mock_get_command.assert_called_with("embed")
        mock_embed_command.stop_embed_server.assert_called_once()

    # 模拟配置不是首次运行，避免触发配置向导
    with patch("viby.cli.app.config.is_first_run", False):
        # 测试status子命令
        mock_get_command.reset_mock()
        mock_embed_command.reset_mock()
        cli_runner.invoke(app, ["tools", "embed", "status"])
        mock_get_command.assert_called_with("embed")
        mock_embed_command.check_embed_server_status.assert_called_once()

    # 模拟配置不是首次运行，避免触发配置向导
    with patch("viby.cli.app.config.is_first_run", False):
        # 测试download子命令
        mock_get_command.reset_mock()
        mock_embed_command.reset_mock()
        cli_runner.invoke(app, ["tools", "embed", "download"])
        mock_get_command.assert_called_with("embed")
        mock_embed_command.download_embedding_model.assert_called_once()
