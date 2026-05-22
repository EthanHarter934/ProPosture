"""pywebview JavaScript bridge for the React desktop UI."""

from __future__ import annotations

from typing import Any

from backend.controller import AppController


class DesktopApi:
    """Methods exposed to React as window.pywebview.api."""

    def __init__(self, controller: AppController) -> None:
        self._controller = controller

    def get_state(self) -> dict[str, Any]:
        return self._controller.state()

    def set_view(self, view: str) -> dict[str, Any]:
        return self._controller.set_view(view)

    def start_monitoring(self) -> dict[str, Any]:
        return self._controller.start_monitoring()

    def stop_monitoring(self) -> dict[str, Any]:
        return self._controller.stop_monitoring()

    def toggle_monitoring(self) -> dict[str, Any]:
        return self._controller.toggle_monitoring()

    def snooze(self) -> dict[str, Any]:
        return self._controller.snooze()

    def resume_alerts(self) -> dict[str, Any]:
        return self._controller.resume_alerts()

    def toggle_pause(self) -> dict[str, Any]:
        return self._controller.toggle_pause()

    def save_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        return self._controller.save_settings(updates)

    def reset_settings(self) -> dict[str, Any]:
        return self._controller.reset_settings()

    def save_sensitivity(self, measurement: str, value: float) -> dict[str, Any]:
        return self._controller.save_sensitivity(measurement, value)

    def test_voice(self, personality: str, voice: str) -> dict[str, Any]:
        return self._controller.test_voice(personality, voice)

    def generate_custom_voice(self, voice_description: str, voice_server_url: str) -> dict[str, Any]:
        return self._controller.generate_custom_voice(voice_description, voice_server_url)

    def generate_custom_voice_test(self, voice_description: str, voice_server_url: str) -> dict[str, Any]:
        return self._controller.generate_custom_voice_test(voice_description, voice_server_url)

    def test_cloned_voice(self, character_description: str, voice_server_url: str) -> dict[str, Any]:
        return self._controller.test_cloned_voice(character_description, voice_server_url)

    def begin_calibration(self) -> dict[str, Any]:
        return self._controller.begin_calibration()

    def start_calibration_preview(self) -> dict[str, Any]:
        return self._controller.start_calibration_preview()

    def start_calibration_capture(self) -> dict[str, Any]:
        return self._controller.start_calibration_capture()

    def accept_calibration(self) -> dict[str, Any]:
        return self._controller.accept_calibration()

    def recapture(self) -> dict[str, Any]:
        return self._controller.recapture()

    def cancel_calibration(self) -> dict[str, Any]:
        return self._controller.cancel_calibration()

    def delete_calibration(self) -> dict[str, Any]:
        return self._controller.delete_calibration()

    def latest_monitor_frame(self) -> str | None:
        return self._controller.latest_monitor_frame_data_url()

    def latest_calibration_frame(self) -> str | None:
        return self._controller.latest_calibration_frame_data_url()

