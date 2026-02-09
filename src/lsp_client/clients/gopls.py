from __future__ import annotations

import shutil
from functools import partial
from pathlib import Path
from subprocess import CalledProcessError
from typing import Any, override

import anyio
from attrs import define
from loguru import logger

from lsp_client.capability.notification import WithNotifyDidChangeConfiguration
from lsp_client.capability.request import (
    WithRequestCallHierarchy,
    WithRequestCodeAction,
    WithRequestCompletion,
    WithRequestDefinition,
    WithRequestDocumentSymbol,
    WithRequestHover,
    WithRequestImplementation,
    WithRequestInlayHint,
    WithRequestReferences,
    WithRequestSignatureHelp,
    WithRequestTypeDefinition,
    WithRequestTypeHierarchy,
    WithRequestWorkspaceSymbol,
)
from lsp_client.capability.server_notification import (
    WithReceiveLogMessage,
    WithReceiveLogTrace,
    WithReceivePublishDiagnostics,
    WithReceiveShowMessage,
)
from lsp_client.capability.server_request import (
    WithRespondConfigurationRequest,
    WithRespondInlayHintRefresh,
    WithRespondShowDocumentRequest,
    WithRespondShowMessageRequest,
    WithRespondWorkspaceFoldersRequest,
)
from lsp_client.clients.base import GoClientBase
from lsp_client.server import DefaultServers, ServerInstallationError
from lsp_client.server.container import ContainerServer
from lsp_client.server.local import LocalServer
from lsp_client.utils.types import lsp_type

GoplsContainerServer = partial(ContainerServer, image="ghcr.io/lsp-client/gopls:latest")


async def ensure_gopls_installed() -> str | None:
    if path := shutil.which("gopls"):
        return path

    logger.warning("gopls not found, attempting to install via go install...")

    try:
        await anyio.run_process(["go", "install", "golang.org/x/tools/gopls@latest"])
        logger.info("Successfully installed gopls via go install")
    except CalledProcessError as e:
        raise ServerInstallationError(
            "Could not install gopls. Please install it manually with 'go install golang.org/x/tools/gopls@latest'. "
            "See https://github.com/golang/tools/tree/master/gopls for more information."
        ) from e

    # go install places binaries in $GOPATH/bin; resolve the actual path
    # since the daemon process may not have it in PATH.
    if path := shutil.which("gopls"):
        return path

    try:
        result = await anyio.run_process(["go", "env", "GOPATH"])
        gopath = result.stdout.decode().strip()
        candidate = Path(gopath) / "bin" / "gopls"
        if candidate.is_file():
            logger.info("Resolved gopls at {}", candidate)
            return str(candidate)
    except (CalledProcessError, OSError):
        pass

    return None


GoplsLocalServer = partial(
    LocalServer,
    program="gopls",
    args=["serve"],
    ensure_installed=ensure_gopls_installed,
)


@define
class GoplsClient(
    GoClientBase,
    WithNotifyDidChangeConfiguration,
    WithRequestCallHierarchy,
    WithRequestCodeAction,
    WithRequestCompletion,
    WithRequestDefinition,
    WithRequestDocumentSymbol,
    WithRequestHover,
    WithRequestImplementation,
    WithRequestInlayHint,
    WithRequestReferences,
    WithRequestSignatureHelp,
    WithRequestTypeDefinition,
    WithRequestTypeHierarchy,
    WithRequestWorkspaceSymbol,
    WithReceiveLogMessage,
    WithReceiveLogTrace,
    WithReceivePublishDiagnostics,
    WithReceiveShowMessage,
    WithRespondConfigurationRequest,
    WithRespondInlayHintRefresh,
    WithRespondShowDocumentRequest,
    WithRespondShowMessageRequest,
    WithRespondWorkspaceFoldersRequest,
):
    """
    - Language: Go
    - Homepage: https://pkg.go.dev/golang.org/x/tools/gopls
    - Doc: https://github.com/golang/tools/blob/master/gopls/README.md
    - Github: https://github.com/golang/tools/tree/master/gopls
    - VSCode Extension: https://marketplace.visualstudio.com/items?itemName=golang.go
    """

    @classmethod
    @override
    def create_default_servers(cls) -> DefaultServers:
        return DefaultServers(
            local=GoplsLocalServer(),
            container=GoplsContainerServer(),
        )

    @override
    def check_server_compatibility(self, info: lsp_type.ServerInfo | None) -> None:
        return

    @override
    def create_default_config(self) -> dict[str, Any] | None:
        """
        https://go.googlesource.com/tools/+/refs/heads/gopls-release-branch.0.5/gopls/doc/settings.md#settings
        """

        return {
            "gopls": {
                # https://go.dev/gopls/inlayHints
                "hints": {
                    "assignVariableTypes": True,
                    "compositeLiteralFields": True,
                    "compositeLiteralTypes": True,
                    "constantValues": True,
                    "functionTypeParameters": True,
                    "parameterNames": True,
                    "rangeVariableTypes": True,
                },
                # https://go.dev/gopls/settings#diagnosticsdelay-timeduration
                "diagnosticsDelay": "100ms",
                "matcher": "Fuzzy",
                "usePlaceholders": True,
                "semanticTokens": True,
            }
        }
