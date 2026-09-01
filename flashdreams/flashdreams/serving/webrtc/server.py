# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack
from importlib.resources import as_file
from pathlib import Path
from typing import Any, Protocol

from aiohttp import web
from loguru import logger

_PROCESS_STARTED_AT = time.time()
"""Captured at import time -- lets ``/healthz`` show a live process's actual
start time, so a browser-only check (no SSH access needed) can confirm
whether a restart picked up a given code change."""


def _file_cache_version(path: Path) -> int:
    """Cache-busting token derived from a static file's own mtime.

    Using the file's modification time (rather than a hand-maintained
    version string) means every edit to adapter.js/adapter.css is
    automatically served fresh -- a hardcoded ``?v=...`` constant silently
    stops busting the browser cache the moment someone edits the file
    without remembering to bump it too.
    """
    return int(path.stat().st_mtime)


class SessionBusyError(RuntimeError):
    """Raised when a second peer tries to open a single-session server."""


class SessionNotActiveError(RuntimeError):
    """Raised when an operation needs an active session but there isn't one."""


class WebRTCSessionManager(Protocol):
    def has_active_session(self) -> bool: ...
    def is_runtime_ready(self) -> bool: ...
    async def preload_runtime(self) -> None: ...
    async def create_answer(
        self, *, offer_sdp: str, offer_type: str
    ) -> dict[str, str]: ...
    async def shutdown(self) -> None: ...


SESSION_MANAGER_KEY = web.AppKey("session_manager", WebRTCSessionManager)
PACKAGE_RESOURCE_STACK_KEY = web.AppKey("package_resource_stack", ExitStack)


def create_webrtc_app(
    *,
    web_dir: Path,
    model_web_dir: Path | None = None,
    session_manager: WebRTCSessionManager,
    request_session_url: str,
    index_filename: str = "request_session.html",
    preload_name: str = "WebRTC",
) -> web.Application:
    app = web.Application()
    app[SESSION_MANAGER_KEY] = session_manager

    async def request_session_page(_: web.Request) -> web.StreamResponse:
        return web.FileResponse(web_dir / index_filename)

    async def offer(request: web.Request) -> web.StreamResponse:
        try:
            payload = await request.json()
        except Exception as exc:
            raise web.HTTPBadRequest(reason="Expected JSON offer payload.") from exc

        if not isinstance(payload, dict):
            raise web.HTTPBadRequest(reason="Offer payload must be a JSON object.")

        sdp = payload.get("sdp")
        offer_type = payload.get("type")
        if not isinstance(sdp, str) or not sdp:
            raise web.HTTPBadRequest(
                reason="Offer payload must include non-empty 'sdp'."
            )
        if not isinstance(offer_type, str) or not offer_type:
            raise web.HTTPBadRequest(
                reason="Offer payload must include non-empty 'type'."
            )

        manager = request.app[SESSION_MANAGER_KEY]
        try:
            answer_payload = await manager.create_answer(
                offer_sdp=sdp,
                offer_type=offer_type,
            )
        except SessionBusyError as exc:
            raise web.HTTPConflict(reason=str(exc)) from exc
        except Exception as exc:
            logger.exception("Failed to process WebRTC offer.")
            raise web.HTTPInternalServerError(reason=str(exc)) from exc

        return web.json_response(answer_payload)

    async def session_event(request: web.Request) -> web.StreamResponse:
        """Trigger a text event on the active session without a WebRTC peer.

        Lets a lightweight second client (e.g. a "director" role) drive
        events on the one live session without needing its own video
        connection -- the server still only ever has one active
        RTCPeerConnection, this just gives a second HTTP-only caller a way
        to feed it events the same way the connected peer's datachannel
        does.
        """
        trigger = getattr(session_manager, "trigger_event", None)
        if not callable(trigger):
            raise web.HTTPNotImplemented(
                reason="This runtime does not support HTTP-triggered events."
            )
        try:
            payload = await request.json()
        except Exception as exc:
            raise web.HTTPBadRequest(reason="Expected JSON event payload.") from exc
        if not isinstance(payload, dict):
            raise web.HTTPBadRequest(reason="Event payload must be a JSON object.")
        try:
            result = await trigger(payload)
        except SessionNotActiveError as exc:
            raise web.HTTPConflict(reason=str(exc)) from exc
        except ValueError as exc:
            raise web.HTTPBadRequest(reason=str(exc)) from exc
        return web.json_response(result)

    async def healthz(request: web.Request) -> web.StreamResponse:
        manager = request.app[SESSION_MANAGER_KEY]
        return web.json_response(
            {
                "status": "ok",
                "runtime_ready": manager.is_runtime_ready(),
                "session_active": manager.has_active_session(),
                "pid": os.getpid(),
                "process_started_at": _PROCESS_STARTED_AT,
                "process_uptime_s": round(time.time() - _PROCESS_STARTED_AT, 1),
            }
        )

    async def ui_config(_: web.Request) -> web.StreamResponse:
        payload: dict[str, object] = {"adapter_module": None}
        adapter_js_path = model_web_dir / "adapter.js" if model_web_dir is not None else None
        if adapter_js_path is not None and adapter_js_path.is_file():
            payload["adapter_module"] = (
                f"/model-static/adapter.js?v={_file_cache_version(adapter_js_path)}"
            )
        adapter_css_path = model_web_dir / "adapter.css" if model_web_dir is not None else None
        if adapter_css_path is not None and adapter_css_path.is_file():
            payload["model_stylesheet"] = (
                f"/model-static/adapter.css?v={_file_cache_version(adapter_css_path)}"
            )
        manager_config = getattr(session_manager, "browser_ui_config", None)
        if callable(manager_config):
            payload.update(manager_config())
        return web.json_response(payload)

    async def on_startup(app: web.Application) -> None:
        manager = app[SESSION_MANAGER_KEY]
        logger.info("Preloading {} runtime on startup.", preload_name)
        await manager.preload_runtime()
        logger.info("{} runtime preload complete.", preload_name)
        print(f"Connect via {request_session_url}")

    async def on_shutdown(app: web.Application) -> None:
        manager = app[SESSION_MANAGER_KEY]
        logger.info("Shutting down {} runtime.", preload_name)
        await manager.shutdown()

    app.router.add_get("/request_session", request_session_page)
    app.router.add_post("/api/webrtc/offer", offer)
    app.router.add_post("/api/session/event", session_event)
    app.router.add_get("/healthz", healthz)
    app.router.add_get("/api/ui/config", ui_config)
    app.router.add_static("/static/", web_dir, show_index=False)
    if model_web_dir is not None:
        app.router.add_static("/model-static/", model_web_dir, show_index=False)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app


async def close_package_resources(app: web.Application) -> None:
    app[PACKAGE_RESOURCE_STACK_KEY].close()


def create_packaged_webrtc_app(
    *,
    web_resource: Any,
    model_web_resource: Any | None = None,
    session_manager: WebRTCSessionManager,
    request_session_url: str,
    preload_name: str,
    configure_app: Callable[[web.Application], None] | None = None,
    index_filename: str = "request_session.html",
    as_file_fn: Callable[[Any], AbstractContextManager[Path]] = as_file,
    create_app_fn: Callable[..., web.Application] = create_webrtc_app,
    cleanup_callback: Callable[[web.Application], Any] = close_package_resources,
) -> web.Application:
    """Create a WebRTC app from packaged static assets.

    ``importlib.resources.as_file`` can materialize package resources into a
    temporary directory. The returned app owns that context until aiohttp
    cleanup, so demos can serve static browser assets from packages and tests
    can still inspect the materialized directory.
    """
    resource_stack = ExitStack()
    try:
        web_dir = resource_stack.enter_context(as_file_fn(web_resource))
        create_kwargs: dict[str, Any] = {
            "web_dir": web_dir,
            "session_manager": session_manager,
            "preload_name": preload_name,
            "request_session_url": request_session_url,
            "index_filename": index_filename,
        }
        if model_web_resource is not None:
            create_kwargs["model_web_dir"] = resource_stack.enter_context(
                as_file_fn(model_web_resource)
            )
        app = create_app_fn(**create_kwargs)
        if configure_app is not None:
            configure_app(app)
        app[PACKAGE_RESOURCE_STACK_KEY] = resource_stack
        app.on_cleanup.append(cleanup_callback)
    except Exception:
        resource_stack.close()
        raise
    return app


__all__ = [
    "SessionBusyError",
    "WebRTCSessionManager",
    "create_packaged_webrtc_app",
    "create_webrtc_app",
]
