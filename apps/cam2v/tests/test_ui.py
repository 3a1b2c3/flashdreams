# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""CPU tests for Cam2V overlay input handling and the postprocess toggle."""

import queue
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from numpy import uint64

from cam2v.ui import Cam2VSlangPyUILoop, Cam2VUIState, _apply_ui_input
from flashdreams.runtime_v2.presentation_manager import PresentationManager
from flashdreams.runtime_v2.session_desc import SessionDesc
from flashdreams.runtime_v2.user_input_event import (
    FocusUserInputEvent,
    KeyboardInputState,
    KeyboardUserInputEvent,
)
from flashdreams.runtime_v2.user_input_events import UserInputEvents

pytestmark = pytest.mark.ci_cpu


def _state(**overrides: object) -> Cam2VUIState:
    defaults: dict[str, object] = {
        "total_blocks": 4,
        "target_fps": 16,
        "warmup_blocks": 1,
    }
    defaults.update(overrides)
    return Cam2VUIState(**defaults)


def _loop(state: Cam2VUIState) -> Cam2VSlangPyUILoop:
    loop = Cam2VSlangPyUILoop(renderer=Mock())
    loop.register_session_loop_objects(
        state=state,
        frequency=60,
        shutdown_event=threading.Event(),
        failure_queue=queue.Queue(),
    )
    loop.register_session_ui_loop_objects(
        session_desc=SessionDesc(),
        presentation_manager=PresentationManager(),
    )
    return loop


def test_apply_ui_input_tracks_held_keys_from_keyboard_events() -> None:
    state = _state()

    _apply_ui_input(
        state,
        UserInputEvents(
            [
                KeyboardUserInputEvent(
                    timestamp=uint64(0), key="w", state=KeyboardInputState.PRESSED
                )
            ]
        ),
    )

    assert state.held_keys == {"w"}


def test_apply_ui_input_releases_a_held_key_on_keyup() -> None:
    state = _state()
    _apply_ui_input(
        state,
        UserInputEvents(
            [
                KeyboardUserInputEvent(
                    timestamp=uint64(0), key="w", state=KeyboardInputState.PRESSED
                )
            ]
        ),
    )

    _apply_ui_input(
        state,
        UserInputEvents(
            [
                KeyboardUserInputEvent(
                    timestamp=uint64(1), key="w", state=KeyboardInputState.RELEASED
                )
            ]
        ),
    )

    assert state.held_keys == set()


def test_apply_ui_input_ignores_unsupported_keys() -> None:
    state = _state()

    _apply_ui_input(
        state,
        UserInputEvents(
            [
                KeyboardUserInputEvent(
                    timestamp=uint64(0), key="z", state=KeyboardInputState.PRESSED
                )
            ]
        ),
    )

    assert state.held_keys == set()


def test_apply_ui_input_clears_held_keys_on_focus_loss() -> None:
    state = _state()
    state.held_keys.add("w")

    _apply_ui_input(
        state,
        UserInputEvents([FocusUserInputEvent(timestamp=uint64(0), focused=False)]),
    )

    assert state.held_keys == set()


def test_set_postprocess_enabled_invokes_the_model_loop_when_toggle_is_shown() -> None:
    state = _state(show_postprocess_toggle=True)
    loop = _loop(state)
    model_loop = Mock()
    loop._set_model_loop(model_loop)

    loop.set_postprocess_enabled(True)

    assert state.postprocess_enabled is True
    model_loop._invoke_async.assert_called_once()
    operation = model_loop._invoke_async.call_args.args[0]
    model_state = Mock()
    operation(model_state)
    model_state.set_postprocess_enabled.assert_called_once_with(True)


def test_set_postprocess_enabled_is_ignored_when_the_toggle_is_hidden() -> None:
    state = _state(show_postprocess_toggle=False)
    loop = _loop(state)
    model_loop = Mock()
    loop._set_model_loop(model_loop)

    loop.set_postprocess_enabled(True)

    assert state.postprocess_enabled is False
    model_loop._invoke_async.assert_not_called()


def test_set_postprocess_enabled_is_ignored_when_the_value_is_unchanged() -> None:
    state = _state(show_postprocess_toggle=True, postprocess_enabled=True)
    loop = _loop(state)
    model_loop = Mock()
    loop._set_model_loop(model_loop)

    loop.set_postprocess_enabled(True)

    model_loop._invoke_async.assert_not_called()


def _slangpy_ui() -> SimpleNamespace:
    return SimpleNamespace(
        screen=object(),
        Window=lambda *args, **kwargs: object(),
        Text=lambda parent, text: SimpleNamespace(text=text),
        CheckBox=lambda window, label, value, callback: SimpleNamespace(
            label=label, value=value, callback=callback
        ),
        Button=lambda window, label, callback: SimpleNamespace(
            label=label, callback=callback
        ),
    )


def test_start_new_rollout_requests_a_replacement_session() -> None:
    loop = _loop(_state())

    loop.start_new_rollout()

    requests = loop.flush_ui_loop_requests()
    assert requests is not None
    assert requests.new_session is loop.session_desc


def test_step_ui_creates_a_new_session_button_wired_to_start_new_rollout() -> None:
    state = _state()
    loop = _loop(state)
    ui = _slangpy_ui()

    loop.step_ui(ui, 0, UserInputEvents([]))

    assert state.new_session_button is not None
    assert state.new_session_button.label == "New session"

    state.new_session_button.callback()

    requests = loop.flush_ui_loop_requests()
    assert requests is not None
    assert requests.new_session is loop.session_desc


def test_step_ui_does_not_recreate_the_button_on_later_steps() -> None:
    state = _state()
    loop = _loop(state)
    ui = _slangpy_ui()

    loop.step_ui(ui, 0, UserInputEvents([]))
    first_button = state.new_session_button
    loop.step_ui(ui, 1, UserInputEvents([]))

    assert state.new_session_button is first_button


def test_state_reset_clears_held_keys_and_status() -> None:
    state = _state()
    state.held_keys.add("w")
    state.frames_presented = 12

    state.reset()

    assert state.held_keys == set()
    assert state.status is None
    assert state.frames_presented == 0
