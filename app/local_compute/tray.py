"""Small Windows notification-area controller for an on-demand runtime."""
from __future__ import annotations

import os
import webbrowser
from pathlib import Path
from threading import Event


class WindowsTray:
    def __init__(self, runtime, *, logs_path: Path, open_url: str, quit_requested: Event, restart_requested: Event, profile_label: str = "ZKD Compute") -> None:
        self.runtime, self.logs_path, self.open_url = runtime, logs_path, open_url
        self.quit_requested, self.restart_requested = quit_requested, restart_requested
        self.profile_label = profile_label
        self.icon = None

    def status_text(self) -> str:
        state = self.runtime.state.value.replace("_", " ").title()
        capability = self.runtime.capabilities().get("generation")
        if capability == "MODEL_UNAVAILABLE":
            state = "Model unavailable"
        return f"{self.profile_label} — {state}"

    def start(self) -> None:
        # Imports stay inside this method so --status and protocol validation
        # remain light-weight and packaging failures are explicit at startup.
        import pystray
        from PIL import Image, ImageDraw

        image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((3, 3, 29, 29), radius=6, fill=(23, 23, 23, 255))
        draw.text((10, 7), "Z", fill=(255, 255, 255, 255))
        self.icon = pystray.Icon("ZKDCompute", image, self.status_text(), pystray.Menu(
            pystray.MenuItem("Open ZKD", lambda *_: webbrowser.open(self.open_url)),
            pystray.MenuItem(lambda _item: "Status: " + self.status_text().split(" — ", 1)[-1], None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Restart Compute", lambda *_: self.restart_requested.set()),
            pystray.MenuItem("Open Logs", lambda *_: self._open_logs()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda *_: self.quit_requested.set()),
        ))
        self.icon.run_detached()

    def refresh(self) -> None:
        if self.icon is not None:
            self.icon.title = self.status_text()
            self.icon.update_menu()

    def stop(self) -> None:
        if self.icon is not None:
            self.icon.stop()
            self.icon = None

    def _open_logs(self) -> None:
        self.logs_path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(self.logs_path))  # noqa: S606 - controlled directory
