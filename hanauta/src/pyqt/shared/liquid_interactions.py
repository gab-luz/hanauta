from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QRect,
    QSize,
    Qt,
    QTimer,
    QPropertyAnimation,
)
from PyQt6.QtGui import QCursor, QFont, QFontMetrics, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QLabel,
    QWidget,
)

from pyqt.shared.motion import MotionSystem, SurfaceTransformEffect, TOKENS, easing_enter, easing_exit, easing_hover


@dataclass(frozen=True)
class LiquidInteractionConfig:
    hover_scale: float = 1.045
    proximity_scale: float = 1.075
    press_scale: float = 0.972
    hover_lift: float = 5.0
    proximity_lift: float = 10.0
    settle_delay_ms: int = 70
    proximity_radius: float = 120.0
    tooltip_rise: int = 8
    indicator_height: int = 4
    indicator_width: int = 18


class LiquidTooltipBubble(QLabel):
    def __init__(self, ui_font: str, motion: MotionSystem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.motion = motion
        self._base_y = 0
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setObjectName("liquidTooltipBubble")
        self.setFont(QFont(ui_font, 10))
        self.setMargin(0)
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self.hide()

    def apply_theme(self, background: str, border: str, text_color: str) -> None:
        self.setStyleSheet(
            f"""
            QLabel#liquidTooltipBubble {{
                background: {background};
                border: 1px solid {border};
                color: {text_color};
                border-radius: 11px;
                padding: 6px 10px;
            }}
            """
        )

    def show_for(self, anchor: QWidget, text: str, rise: int) -> None:
        if not text.strip():
            self.hide_bubble()
            return
        self.setText(text)
        self.adjustSize()
        anchor_top = anchor.mapToGlobal(QPoint(anchor.width() // 2, 0))
        x = anchor_top.x() - self.width() // 2
        self._base_y = anchor_top.y() - self.height() - 10
        self.move(x, self._base_y + rise)
        self.show()
        self.raise_()
        self.motion.animate_opacity(self, None, 1.0, TOKENS.duration_sm, easing_enter, key="liquid:tooltip:opacity")
        self.motion.animate_geometry(
            self,
            self.geometry(),
            QRect(x, self._base_y, self.width(), self.height()),
            TOKENS.duration_sm,
            easing_enter,
            key="liquid:tooltip:geometry",
        )

    def hide_bubble(self) -> None:
        if not self.isVisible():
            return
        self.motion.animate_opacity(self, None, 0.0, TOKENS.duration_xs, easing_exit, key="liquid:tooltip:opacity")
        self.motion.animate_geometry(
            self,
            self.geometry(),
            QRect(self.x(), self._base_y + 6, self.width(), self.height()),
            TOKENS.duration_xs,
            easing_exit,
            key="liquid:tooltip:geometry",
        )
        QTimer.singleShot(TOKENS.duration_xs + 12, self.hide)


class LiquidIndicator(QFrame):
    def __init__(self, motion: MotionSystem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.motion = motion
        self.setObjectName("liquidActiveIndicator")
        self.hide()

    def apply_theme(self, color: str, glow: str) -> None:
        self.setStyleSheet(
            f"""
            QFrame#liquidActiveIndicator {{
                background: {color};
                border: 1px solid {glow};
                border-radius: 999px;
            }}
            """
        )

    def glide_to(self, rect: QRect) -> None:
        target = QRect(rect)
        if not self.isVisible():
            self.setGeometry(target)
            self.show()
            return
        self.motion.animate_geometry(self, self.geometry(), target, TOKENS.duration_sm, easing_enter, key=f"{id(self)}:geometry")


class LiquidInteractionController(QObject):
    def __init__(
        self,
        widget: QWidget,
        motion: MotionSystem,
        *,
        config: LiquidInteractionConfig,
        tooltip: LiquidTooltipBubble | None = None,
    ) -> None:
        super().__init__(widget)
        self.widget = widget
        self.motion = motion
        self.config = config
        self.tooltip = tooltip
        self.effect = self._ensure_effect(widget)
        self._hovered = False
        self._pressed = False
        self._proximity = 0.0
        self._settle_timer = QTimer(self)
        self._settle_timer.setSingleShot(True)
        self._settle_timer.timeout.connect(self._retarget_visuals)
        widget.setMouseTracking(True)
        widget.installEventFilter(self)

    def set_proximity(self, amount: float) -> None:
        amount = max(0.0, min(1.0, float(amount)))
        if abs(amount - self._proximity) < 0.01:
            return
        self._proximity = amount
        if not self._hovered and not self._pressed:
            self._retarget_visuals()

    def eventFilter(self, watched: QObject, event) -> bool:  # type: ignore[override]
        if watched is not self.widget:
            return super().eventFilter(watched, event)
        event_type = event.type()
        if event_type == QEvent.Type.Enter:
            self._hovered = True
            self._settle_timer.stop()
            self._retarget_visuals()
            if self.tooltip is not None:
                self.tooltip.show_for(self.widget, self.widget.toolTip(), self.config.tooltip_rise)
        elif event_type == QEvent.Type.Leave:
            self._hovered = False
            self._pressed = False
            self._settle_timer.start(self.config.settle_delay_ms)
            if self.tooltip is not None:
                self.tooltip.hide_bubble()
        elif event_type == QEvent.Type.MouseButtonPress:
            self._pressed = True
            self._settle_timer.stop()
            self._retarget_visuals()
        elif event_type == QEvent.Type.MouseButtonRelease:
            self._pressed = False
            self._retarget_visuals()
        return super().eventFilter(watched, event)

    def _ensure_effect(self, widget: QWidget) -> SurfaceTransformEffect:
        effect = widget.graphicsEffect()
        if isinstance(effect, SurfaceTransformEffect):
            return effect
        if effect is not None:
            raise RuntimeError("Liquid interactions require a free graphics effect slot")
        created = SurfaceTransformEffect(widget)
        widget.setGraphicsEffect(created)
        return created

    def _retarget_visuals(self) -> None:
        proximity_scale = 1.0 + (self.config.proximity_scale - 1.0) * self._proximity
        hover_scale = self.config.hover_scale if self._hovered else 1.0
        target_scale = max(proximity_scale, hover_scale)
        if self._pressed:
            target_scale = min(target_scale, self.config.press_scale)

        proximity_lift = self.config.proximity_lift * self._proximity
        hover_lift = self.config.hover_lift if self._hovered else 0.0
        target_y = -max(proximity_lift, hover_lift)
        if self._pressed:
            target_y *= 0.35

        easing = easing_hover if (self._hovered or self._proximity > 0.05) and not self._pressed else easing_enter
        duration = TOKENS.duration_sm if (self._hovered or self._pressed or self._proximity > 0.05) else TOKENS.duration_md
        self.motion.animate_float(self.effect, "scale", None, target_scale, duration, easing, key=f"{id(self.effect)}:scale")
        self.motion.animate_float(self.effect, "yOffset", None, target_y, duration, easing, key=f"{id(self.effect)}:y")


class LiquidProximityManager(QObject):
    def __init__(
        self,
        host: QWidget,
        motion: MotionSystem,
        *,
        config: LiquidInteractionConfig | None = None,
        tooltip: LiquidTooltipBubble | None = None,
    ) -> None:
        super().__init__(host)
        self.host = host
        self.motion = motion
        self.config = config or LiquidInteractionConfig()
        self.tooltip = tooltip
        self._items: list[LiquidInteractionController] = []
        self._by_widget: dict[int, LiquidInteractionController] = {}
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self.motion.capability.proximity_interval_ms)
        self._poll_timer.timeout.connect(self._update_proximity)
        self._last_cursor = QPoint(-10_000, -10_000)
        host.setMouseTracking(True)
        host.installEventFilter(self)

    def add_widget(self, widget: QWidget) -> LiquidInteractionController:
        widget_id = id(widget)
        existing = self._by_widget.get(widget_id)
        if existing is not None:
            return existing
        controller = LiquidInteractionController(widget, self.motion, config=self.config, tooltip=self.tooltip)
        controller._widget_id = widget_id  # type: ignore[attr-defined]
        self._items.append(controller)
        self._by_widget[widget_id] = controller
        widget.destroyed.connect(lambda _obj=None, widget_id=widget_id: self._remove_widget(widget_id))
        return controller

    def set_active_indicator(self, indicator: LiquidIndicator, active_widget: QWidget | None, *, width: int, height: int, bottom_margin: int = 0) -> None:
        if active_widget is None:
            indicator.hide()
            return
        center = active_widget.geometry().center()
        target = QRect(
            int(center.x() - width / 2),
            active_widget.geometry().bottom() - height - bottom_margin,
            width,
            height,
        )
        indicator.glide_to(target)

    def eventFilter(self, watched: QObject, event) -> bool:  # type: ignore[override]
        if watched is self.host:
            if event.type() == QEvent.Type.Enter:
                if not self._poll_timer.isActive():
                    self._poll_timer.start()
            elif event.type() == QEvent.Type.Leave:
                for item in list(self._items):
                    item.set_proximity(0.0)
                self._poll_timer.stop()
                if self.tooltip is not None:
                    self.tooltip.hide_bubble()
        return super().eventFilter(watched, event)

    def _update_proximity(self) -> None:
        if not self.host.isVisible():
            return
        cursor = self.host.mapFromGlobal(QCursor.pos())
        if cursor == self._last_cursor:
            return
        self._last_cursor = QPoint(cursor)
        radius = max(1.0, self.config.proximity_radius)
        stale_ids: list[int] = []
        for item in list(self._items):
            try:
                widget = item.widget
                rect = widget.geometry()
            except RuntimeError:
                stale_ids.append(getattr(item, "_widget_id", 0))
                continue
            center = rect.center()
            dx = float(cursor.x() - center.x())
            dy = float(cursor.y() - center.y())
            distance = (dx * dx + dy * dy) ** 0.5
            amount = max(0.0, min(1.0, 1.0 - (distance / radius)))
            item.set_proximity(amount)
        for widget_id in stale_ids:
            if widget_id:
                self._remove_widget(widget_id)

    def _remove_widget(self, widget_id: int) -> None:
        controller = self._by_widget.pop(widget_id, None)
        if controller is None:
            return
        try:
            self._items.remove(controller)
        except ValueError:
            pass


def compact_tooltip_width(font: QFont, text: str, max_width: int = 220) -> int:
    metrics = QFontMetrics(font)
    return min(max_width, metrics.horizontalAdvance(text) + 20)
