import pytest
from unittest.mock import MagicMock, patch
from webui.runner import build_cli_parser, main, launch_modern_webui


def test_cli_parser_defaults():
    parser = build_cli_parser()
    args = parser.parse_args([])
    assert args.colab is False
    assert args.tunnel is None
    assert args.legacy_gradio is False
    assert args.host is None
    assert args.port is None


def test_cli_parser_colab_flag():
    parser = build_cli_parser()
    args = parser.parse_args(["--colab"])
    assert args.colab is True


def test_cli_parser_tunnel_options():
    parser = build_cli_parser()
    args_cf = parser.parse_args(["--tunnel", "cloudflare"])
    assert args_cf.tunnel == "cloudflare"

    args_none = parser.parse_args(["--tunnel", "none"])
    assert args_none.tunnel == "none"

    args_gradio = parser.parse_args(["--tunnel", "gradio"])
    assert args_gradio.tunnel == "gradio"


def test_cli_parser_legacy_gradio_flag():
    parser = build_cli_parser()
    args = parser.parse_args(["--legacy-gradio"])
    assert args.legacy_gradio is True


def test_cli_parser_custom_host_port():
    parser = build_cli_parser()
    args = parser.parse_args(["--host", "127.0.0.1", "--port", "9000"])
    assert args.host == "127.0.0.1"
    assert args.port == 9000


def test_main_modern_webui_default():
    with patch("webui.runner.launch_modern_webui") as mock_modern, \
         patch("webui.runner.launch_legacy_gradio", create=True) as mock_legacy:
        main([])
        mock_modern.assert_called_once()
        call_args, call_kwargs = mock_modern.call_args
        assert call_kwargs["tunnel_type"] == "none"


def test_main_colab_defaults_tunnel_cloudflare():
    with patch("webui.runner.launch_modern_webui") as mock_modern:
        main(["--colab"])
        mock_modern.assert_called_once()
        _, kwargs = mock_modern.call_args
        assert kwargs["host"] == "0.0.0.0"
        assert kwargs["port"] == 7860
        assert kwargs["tunnel_type"] == "cloudflare"


def test_main_colab_explicit_tunnel_none():
    with patch("webui.runner.launch_modern_webui") as mock_modern:
        main(["--colab", "--tunnel", "none"])
        mock_modern.assert_called_once()
        _, kwargs = mock_modern.call_args
        assert kwargs["tunnel_type"] == "none"


def test_main_legacy_gradio_dispatch():
    with patch("webui.runner.launch_modern_webui") as mock_modern, \
         patch("webui.app.launch_legacy_gradio") as mock_legacy:
        main(["--legacy-gradio", "--colab"])
        mock_modern.assert_not_called()
        mock_legacy.assert_called_once()
        _, kwargs = mock_legacy.call_args
        assert kwargs["host"] == "0.0.0.0"
        assert kwargs["port"] == 7860
        assert kwargs["tunnel_type"] == "cloudflare"


def test_launch_modern_webui_lifecycle():
    mock_tunnel_cls = MagicMock()
    mock_tunnel_instance = MagicMock()
    mock_tunnel_cls.return_value = mock_tunnel_instance
    mock_tunnel_instance.start.return_value = "https://test.trycloudflare.com"

    with patch("webui.runner.CloudflaredTunnel", mock_tunnel_cls), \
         patch("uvicorn.run") as mock_uvicorn, \
         patch("webui.runner.ensure_frontend_built"):
        parser = build_cli_parser()
        args = parser.parse_args(["--colab", "--tunnel", "cloudflare"])
        launch_modern_webui(args, host="0.0.0.0", port=7860, tunnel_type="cloudflare")

        mock_tunnel_cls.assert_called_once_with(port=7860, host="127.0.0.1")
        mock_tunnel_instance.start.assert_called_once()
        mock_uvicorn.assert_called_once()
        mock_tunnel_instance.stop.assert_called_once()
