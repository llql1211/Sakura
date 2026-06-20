from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication


def capture_virtual_desktop_pixmap() -> tuple[QPixmap, QRect]:
    """截取所有屏幕合并后的虚拟桌面。"""

    screens = QApplication.screens()
    if not screens:
        raise RuntimeError("无法找到可截图的屏幕。")

    virtual_geometry = QRect()
    for screen in screens:
        virtual_geometry = virtual_geometry.united(screen.geometry())
    if virtual_geometry.isNull():
        raise RuntimeError("无法获取虚拟桌面区域。")

    # 按物理像素分配缓冲区，避免高 DPI 缩放导致截图模糊。
    # 逻辑尺寸仍等于 virtual_geometry.size()，下游按逻辑坐标操作无需改动。
    max_dpr = max(s.devicePixelRatio() for s in screens)
    phys_w = round(virtual_geometry.width() * max_dpr)
    phys_h = round(virtual_geometry.height() * max_dpr)
    desktop_pixmap = QPixmap(phys_w, phys_h)
    desktop_pixmap.setDevicePixelRatio(max_dpr)
    desktop_pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(desktop_pixmap)
    captured_count = 0
    for screen in screens:
        screen_pixmap = screen.grabWindow(0)
        if screen_pixmap.isNull():
            continue
        target_rect = QRect(
            screen.geometry().topLeft() - virtual_geometry.topLeft(),
            screen.geometry().size(),
        )
        painter.drawPixmap(target_rect, screen_pixmap)
        captured_count += 1
    painter.end()

    if captured_count == 0:
        raise RuntimeError("屏幕截图为空，可能被系统权限或显示环境阻止。")
    return desktop_pixmap, virtual_geometry
