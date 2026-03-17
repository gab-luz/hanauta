from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QEvent, QObject, QPointF, QRectF, Qt, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PyQt6.QtWidgets import QAbstractButton, QFrame, QSlider, QWidget

from pyqt.shared.motion import MotionSystem, SurfaceTransformEffect, TOKENS


def _blend(a: QColor, b: QColor, factor: float) -> QColor:
    amount = max(0.0, min(1.0, float(factor)))
    return QColor(
        int(a.red() + (b.red() - a.red()) * amount),
        int(a.green() + (b.green() - a.green()) * amount),
        int(a.blue() + (b.blue() - a.blue()) * amount),
        int(a.alpha() + (b.alpha() - a.alpha()) * amount),
    )


def _with_alpha(color: QColor, alpha: float) -> QColor:
    value = QColor(color)
    value.setAlphaF(max(0.0, min(1.0, float(alpha))))
    return value


@dataclass(frozen=True)
class LiquidChromeColors:
    fill: QColor
    active_fill: QColor
    border: QColor
    accent: QColor
    shadow: QColor
    text: QColor
    text_active: QColor
    text_muted: QColor


@dataclass(frozen=True)
class LiquidChromeMetrics:
    radius: float = 18.0
    padding: float = 1.5
    hover_scale: float = 1.015
    pressed_scale: float = 0.988
    active_scale: float = 1.0
    hover_lift: float = 2.0
    pressed_lift: float = 0.25
    shadow_depth: float = 8.0
    shadow_softness: float = 12.0


class LiquidChromeProxy(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fill_mix = 0.0
        self._border_emphasis = 0.12
        self._highlight_strength = 0.04
        self._highlight_position = 0.5
        self._shadow_strength = 0.12
        self._shadow_offset = 2.0
        self._content_opacity = 1.0

    @pyqtProperty(float)
    def fillMix(self) -> float:
        return self._fill_mix

    @fillMix.setter
    def fillMix(self, value: float) -> None:
        self._fill_mix = max(0.0, min(1.0, float(value)))
        self._refresh()

    @pyqtProperty(float)
    def borderEmphasis(self) -> float:
        return self._border_emphasis

    @borderEmphasis.setter
    def borderEmphasis(self, value: float) -> None:
        self._border_emphasis = max(0.0, min(1.0, float(value)))
        self._refresh()

    @pyqtProperty(float)
    def highlightStrength(self) -> float:
        return self._highlight_strength

    @highlightStrength.setter
    def highlightStrength(self, value: float) -> None:
        self._highlight_strength = max(0.0, min(1.0, float(value)))
        self._refresh()

    @pyqtProperty(float)
    def highlightPosition(self) -> float:
        return self._highlight_position

    @highlightPosition.setter
    def highlightPosition(self, value: float) -> None:
        self._highlight_position = max(0.0, min(1.0, float(value)))
        self._refresh()

    @pyqtProperty(float)
    def shadowStrength(self) -> float:
        return self._shadow_strength

    @shadowStrength.setter
    def shadowStrength(self, value: float) -> None:
        self._shadow_strength = max(0.0, min(1.0, float(value)))
        self._refresh()

    @pyqtProperty(float)
    def shadowOffset(self) -> float:
        return self._shadow_offset

    @shadowOffset.setter
    def shadowOffset(self, value: float) -> None:
        self._shadow_offset = float(value)
        self._refresh()

    @pyqtProperty(float)
    def contentOpacity(self) -> float:
        return self._content_opacity

    @contentOpacity.setter
    def contentOpacity(self, value: float) -> None:
        self._content_opacity = max(0.0, min(1.0, float(value)))
        self._refresh()

    def _refresh(self) -> None:
        parent = self.parent()
        if isinstance(parent, QWidget):
            parent.update()


class LiquidChromeMixin:
    def _init_liquid_chrome(self, motion: MotionSystem | None, colors: LiquidChromeColors, metrics: LiquidChromeMetrics) -> None:
        self._liquid_motion = motion or MotionSystem(self)  # type: ignore[attr-defined]
        self._liquid_colors = colors  # type: ignore[attr-defined]
        self._liquid_metrics = metrics  # type: ignore[attr-defined]
        self._liquid_proxy = LiquidChromeProxy(self)  # type: ignore[attr-defined]
        self._liquid_hovered = False  # type: ignore[attr-defined]
        self._liquid_pressed = False  # type: ignore[attr-defined]
        self._liquid_focused = False  # type: ignore[attr-defined]
        self._liquid_effect = SurfaceTransformEffect(self)  # type: ignore[attr-defined]
        casted = self  # type: ignore[assignment]
        casted.setGraphicsEffect(self._liquid_effect)  # type: ignore[attr-defined]
        casted.setMouseTracking(True)  # type: ignore[attr-defined]
        casted.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # type: ignore[attr-defined]
        self._retarget_liquid(immediate=True)  # type: ignore[attr-defined]

    def _content_widgets(self) -> list[QWidget]:
        return []

    def _is_active_state(self) -> bool:
        return False

    def _update_content_appearance(self) -> None:
        for widget in self._content_widgets():
            widget.update()

    def _retarget_liquid(self, *, immediate: bool = False) -> None:
        active = self._is_active_state()
        disabled = not self.isEnabled()  # type: ignore[attr-defined]
        hovered = self._liquid_hovered and not disabled  # type: ignore[attr-defined]
        pressed = self._liquid_pressed and not disabled  # type: ignore[attr-defined]
        focused = self._liquid_focused and not disabled  # type: ignore[attr-defined]

        fill_mix = 0.0
        border = 0.12
        highlight = 0.04
        shadow = 0.12
        shadow_offset = 2.0
        scale = 1.0
        y_offset = 0.0
        content_opacity = 0.98

        if active:
            fill_mix = 0.88
            border = 0.56
            highlight = 0.10
            shadow = 0.22
            shadow_offset = 4.0
            content_opacity = 1.0
            scale = self._liquid_metrics.active_scale  # type: ignore[attr-defined]
            y_offset = -0.6
        if hovered:
            fill_mix = max(fill_mix, 0.22 if not active else fill_mix)
            border = max(border, 0.36)
            highlight = max(highlight, 0.18)
            shadow = max(shadow, 0.18)
            shadow_offset = max(shadow_offset, 4.0)
            scale = self._liquid_metrics.hover_scale  # type: ignore[attr-defined]
            y_offset = -self._liquid_metrics.hover_lift  # type: ignore[attr-defined]
            content_opacity = 1.0
        if pressed:
            border = max(border, 0.46)
            highlight = max(0.10, highlight * 0.72)
            shadow *= 0.6
            shadow_offset = self._liquid_metrics.pressed_lift  # type: ignore[attr-defined]
            scale = self._liquid_metrics.pressed_scale  # type: ignore[attr-defined]
            y_offset = -self._liquid_metrics.pressed_lift  # type: ignore[attr-defined]
        if focused:
            border = max(border, 0.68)
            highlight = max(highlight, 0.16)
        if disabled:
            fill_mix *= 0.25
            border = 0.08
            highlight = 0.0
            shadow = 0.06
            shadow_offset = 1.0
            scale = 1.0
            y_offset = 0.0
            content_opacity = 0.42

        duration = TOKENS.duration_sm if (hovered or pressed or active or focused) else TOKENS.duration_md
        easing = "enter" if immediate else ("emphasis" if hovered and not pressed else "settle")
        if immediate:
            self._liquid_effect.scale = scale  # type: ignore[attr-defined]
            self._liquid_effect.yOffset = y_offset  # type: ignore[attr-defined]
            self._liquid_proxy.fillMix = fill_mix  # type: ignore[attr-defined]
            self._liquid_proxy.borderEmphasis = border  # type: ignore[attr-defined]
            self._liquid_proxy.highlightStrength = highlight  # type: ignore[attr-defined]
            self._liquid_proxy.shadowStrength = shadow  # type: ignore[attr-defined]
            self._liquid_proxy.shadowOffset = shadow_offset  # type: ignore[attr-defined]
            self._liquid_proxy.contentOpacity = content_opacity  # type: ignore[attr-defined]
            self._update_content_appearance()
            return

        key = f"liquid:{id(self)}"
        self._liquid_motion.animate_float(self._liquid_effect, "scale", None, scale, duration, easing, key=f"{key}:scale")  # type: ignore[attr-defined]
        self._liquid_motion.animate_float(self._liquid_effect, "yOffset", None, y_offset, duration, easing, key=f"{key}:y")  # type: ignore[attr-defined]
        self._liquid_motion.animate_float(self._liquid_proxy, "fillMix", None, fill_mix, duration, easing, key=f"{key}:fill")  # type: ignore[attr-defined]
        self._liquid_motion.animate_float(self._liquid_proxy, "borderEmphasis", None, border, duration, easing, key=f"{key}:border")  # type: ignore[attr-defined]
        self._liquid_motion.animate_float(self._liquid_proxy, "highlightStrength", None, highlight, duration, easing, key=f"{key}:highlight")  # type: ignore[attr-defined]
        self._liquid_motion.animate_float(self._liquid_proxy, "shadowStrength", None, shadow, duration, easing, key=f"{key}:shadow")  # type: ignore[attr-defined]
        self._liquid_motion.animate_float(self._liquid_proxy, "shadowOffset", None, shadow_offset, duration, easing, key=f"{key}:shadow-offset")  # type: ignore[attr-defined]
        self._liquid_motion.animate_float(self._liquid_proxy, "contentOpacity", None, content_opacity, duration, easing, key=f"{key}:opacity")  # type: ignore[attr-defined]
        self._update_content_appearance()

    def _update_highlight_position(self, ratio: float) -> None:
        self._liquid_motion.animate_float(
            self._liquid_proxy,  # type: ignore[attr-defined]
            "highlightPosition",
            None,
            ratio,
            TOKENS.duration_xs,
            "enter",
            key=f"liquid:{id(self)}:highlight-pos",
        )

    def _liquid_event(self, event: QEvent) -> None:
        event_type = event.type()
        if event_type == QEvent.Type.Enter:
            self._liquid_hovered = True  # type: ignore[attr-defined]
            self._retarget_liquid()
        elif event_type == QEvent.Type.Leave:
            self._liquid_hovered = False  # type: ignore[attr-defined]
            self._liquid_pressed = False  # type: ignore[attr-defined]
            self._retarget_liquid()
        elif event_type == QEvent.Type.FocusIn:
            self._liquid_focused = True  # type: ignore[attr-defined]
            self._retarget_liquid()
        elif event_type == QEvent.Type.FocusOut:
            self._liquid_focused = False  # type: ignore[attr-defined]
            self._retarget_liquid()
        elif event_type == QEvent.Type.EnabledChange:
            self._retarget_liquid()

    def _paint_liquid_surface(self, painter: QPainter, rect: QRectF) -> None:
        colors = self._liquid_colors  # type: ignore[attr-defined]
        proxy = self._liquid_proxy  # type: ignore[attr-defined]
        metrics = self._liquid_metrics  # type: ignore[attr-defined]
        inner = rect.adjusted(metrics.padding, metrics.padding, -metrics.padding, -metrics.padding)
        shadow_rect = inner.translated(0.0, proxy.shadowOffset)
        shadow_path = QPainterPath()
        shadow_path.addRoundedRect(shadow_rect, metrics.radius + metrics.shadow_softness * 0.1, metrics.radius + metrics.shadow_softness * 0.1)
        shadow_color = _with_alpha(colors.shadow, proxy.shadowStrength)
        painter.fillPath(shadow_path, shadow_color)

        fill = _blend(colors.fill, colors.active_fill, proxy.fillMix)
        top_fill = _blend(fill.lighter(108), colors.accent, proxy.highlightStrength * 0.15)
        panel_path = QPainterPath()
        panel_path.addRoundedRect(inner, metrics.radius, metrics.radius)
        gradient = QLinearGradient(inner.topLeft(), inner.bottomLeft())
        gradient.setColorAt(0.0, top_fill)
        gradient.setColorAt(1.0, fill)
        painter.fillPath(panel_path, gradient)

        width = inner.width()
        highlight_center = inner.left() + width * proxy.highlightPosition
        highlight_rect = QRectF(highlight_center - width * 0.36, inner.top(), width * 0.72, inner.height())
        highlight_path = QPainterPath()
        highlight_path.addRoundedRect(highlight_rect, metrics.radius, metrics.radius)
        highlight_color = _with_alpha(colors.accent, proxy.highlightStrength * 0.23)
        painter.fillPath(highlight_path, highlight_color)

        border_color = _blend(colors.border, colors.accent, proxy.borderEmphasis * 0.58)
        border_color.setAlphaF(min(1.0, 0.22 + proxy.borderEmphasis * 0.55))
        pen = painter.pen()
        pen.setWidthF(1.15 + proxy.borderEmphasis * 0.45)
        pen.setColor(border_color)
        painter.setPen(pen)
        painter.drawPath(panel_path)


class LiquidButtonSurface(QAbstractButton, LiquidChromeMixin):
    def __init__(
        self,
        colors: LiquidChromeColors,
        *,
        motion: MotionSystem | None = None,
        metrics: LiquidChromeMetrics | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(False)
        self._init_liquid_chrome(motion, colors, metrics or LiquidChromeMetrics())

    def _is_active_state(self) -> bool:
        return self.isChecked()

    def event(self, event: QEvent) -> bool:
        self._liquid_event(event)
        return super().event(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.width() > 0:
            self._update_highlight_position(event.position().x() / max(1.0, float(self.width())))
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self._liquid_pressed = event.button() == Qt.MouseButton.LeftButton  # type: ignore[attr-defined]
        self._retarget_liquid()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._liquid_pressed = False  # type: ignore[attr-defined]
        self._retarget_liquid()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        self._paint_liquid_surface(painter, QRectF(self.rect()))
        painter.end()


class LiquidPanelFrame(QFrame, LiquidChromeMixin):
    def __init__(
        self,
        colors: LiquidChromeColors,
        *,
        motion: MotionSystem | None = None,
        metrics: LiquidChromeMetrics | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._active = False
        self._init_liquid_chrome(motion, colors, metrics or LiquidChromeMetrics())

    def set_active_state(self, active: bool) -> None:
        self._active = bool(active)
        self._retarget_liquid()

    def _is_active_state(self) -> bool:
        return self._active

    def event(self, event: QEvent) -> bool:
        self._liquid_event(event)
        return super().event(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.width() > 0:
            self._update_highlight_position(event.position().x() / max(1.0, float(self.width())))
        super().mouseMoveEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        self._paint_liquid_surface(painter, QRectF(self.rect()))
        painter.end()


class LiquidToggleSwitch(QAbstractButton):
    toggledValue = pyqtSignal(bool)

    def __init__(self, checked: bool = False, *, motion: MotionSystem | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.motion = motion or MotionSystem(self)
        self._hovered = False
        self._pressed = False
        self._focused = False
        self._knob_position = 1.0 if checked else 0.0
        self._track_mix = 1.0 if checked else 0.0
        self._handle_scale = 1.0
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(52, 30)
        self.clicked.connect(self._emit_toggled)

    @pyqtProperty(float)
    def knobPosition(self) -> float:
        return self._knob_position

    @knobPosition.setter
    def knobPosition(self, value: float) -> None:
        self._knob_position = max(0.0, min(1.0, float(value)))
        self.update()

    @pyqtProperty(float)
    def trackMix(self) -> float:
        return self._track_mix

    @trackMix.setter
    def trackMix(self, value: float) -> None:
        self._track_mix = max(0.0, min(1.0, float(value)))
        self.update()

    @pyqtProperty(float)
    def handleScale(self) -> float:
        return self._handle_scale

    @handleScale.setter
    def handleScale(self, value: float) -> None:
        self._handle_scale = max(0.84, min(1.08, float(value)))
        self.update()

    def _emit_toggled(self) -> None:
        self._retarget()
        self.toggledValue.emit(self.isChecked())

    def event(self, event: QEvent) -> bool:
        event_type = event.type()
        if event_type == QEvent.Type.Enter:
            self._hovered = True
            self._retarget()
        elif event_type == QEvent.Type.Leave:
            self._hovered = False
            self._pressed = False
            self._retarget()
        elif event_type == QEvent.Type.FocusIn:
            self._focused = True
            self._retarget()
        elif event_type == QEvent.Type.FocusOut:
            self._focused = False
            self._retarget()
        elif event_type == QEvent.Type.EnabledChange:
            self._retarget()
        return super().event(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self._pressed = event.button() == Qt.MouseButton.LeftButton
        self._retarget()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._pressed = False
        self._retarget()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        off_track = QColor(255, 255, 255, 52)
        on_track = QColor(215, 194, 220)
        track = _blend(off_track, on_track, self._track_mix)
        if not self.isEnabled():
            track.setAlpha(52)
        painter.setPen(QColor(255, 255, 255, 28 if self.isEnabled() else 18))
        painter.setBrush(track)
        painter.drawRoundedRect(rect, rect.height() / 2.0, rect.height() / 2.0)

        if self._focused:
            focus = QColor(255, 255, 255, 34)
            painter.setPen(focus)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-1.0, -1.0, 1.0, 1.0), rect.height() / 2.0 + 1.0, rect.height() / 2.0 + 1.0)

        handle_diameter = 22.0 * self._handle_scale
        travel = rect.width() - 8.0 - handle_diameter
        handle_x = rect.left() + 4.0 + travel * self._knob_position
        handle_y = rect.top() + (rect.height() - handle_diameter) / 2.0
        shadow = QColor(0, 0, 0, 34 if self.isEnabled() else 18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow)
        painter.drawEllipse(QRectF(handle_x, handle_y + 1.2, handle_diameter, handle_diameter))
        handle = QColor("#251E2D" if self.isChecked() else "#F6ECFA")
        if not self.isEnabled():
            handle.setAlpha(120)
        painter.setBrush(handle)
        painter.drawEllipse(QRectF(handle_x, handle_y, handle_diameter, handle_diameter))
        painter.end()

    def _retarget(self) -> None:
        duration = TOKENS.duration_sm if (self._hovered or self._pressed or self._focused) else TOKENS.duration_md
        knob = 1.0 if self.isChecked() else 0.0
        track = 1.0 if self.isChecked() else 0.0
        scale = 0.92 if self._pressed else (1.04 if self._hovered else 1.0)
        if not self.isEnabled():
            scale = 0.96
        self.motion.animate_float(self, "knobPosition", None, knob, duration, "settle", key=f"{id(self)}:knob")
        self.motion.animate_float(self, "trackMix", None, track, duration, "enter", key=f"{id(self)}:track")
        self.motion.animate_float(self, "handleScale", None, scale, TOKENS.duration_xs, "enter", key=f"{id(self)}:scale")


class LiquidSlider(QSlider):
    def __init__(self, orientation: Qt.Orientation, *, motion: MotionSystem | None = None, parent: QWidget | None = None) -> None:
        super().__init__(orientation, parent)
        self.motion = motion or MotionSystem(self)
        self._hovered = False
        self._pressed = False
        self._focused = False
        self._handleScale = 1.0
        self._fillGlow = 0.16
        self._handleRatio = 0.0
        self.setMouseTracking(True)
        self.valueChanged.connect(self._sync_ratio)
        self._sync_ratio()

    @pyqtProperty(float)
    def handleScale(self) -> float:
        return self._handleScale

    @handleScale.setter
    def handleScale(self, value: float) -> None:
        self._handleScale = max(0.86, min(1.18, float(value)))
        self.update()

    @pyqtProperty(float)
    def fillGlow(self) -> float:
        return self._fillGlow

    @fillGlow.setter
    def fillGlow(self, value: float) -> None:
        self._fillGlow = max(0.0, min(1.0, float(value)))
        self.update()

    def _sync_ratio(self) -> None:
        span = max(1, self.maximum() - self.minimum())
        self._handleRatio = (self.value() - self.minimum()) / span
        self.update()

    def event(self, event: QEvent) -> bool:
        event_type = event.type()
        if event_type == QEvent.Type.Enter:
            self._hovered = True
            self._retarget()
        elif event_type == QEvent.Type.Leave:
            self._hovered = False
            self._pressed = False
            self._retarget()
        elif event_type == QEvent.Type.FocusIn:
            self._focused = True
            self._retarget()
        elif event_type == QEvent.Type.FocusOut:
            self._focused = False
            self._retarget()
        return super().event(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self._pressed = event.button() == Qt.MouseButton.LeftButton
        self._retarget()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._pressed = False
        self._retarget()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if self.orientation() != Qt.Orientation.Horizontal:
            return super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(7.0, 0.0, -7.0, 0.0)
        groove = QRectF(rect.left(), rect.center().y() - 2.5, rect.width(), 5.0)
        accent = QColor(215, 194, 220)
        track = QColor(255, 255, 255, 42)
        active_width = groove.width() * self._handleRatio
        active = QRectF(groove.left(), groove.top(), active_width, groove.height())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track if self.isEnabled() else QColor(255, 255, 255, 22))
        painter.drawRoundedRect(groove, groove.height() / 2.0, groove.height() / 2.0)
        glow = _with_alpha(accent, 0.16 + self._fillGlow * 0.18)
        painter.setBrush(glow)
        painter.drawRoundedRect(active, groove.height() / 2.0, groove.height() / 2.0)

        handle_radius = 7.0 * self._handleScale
        handle_x = groove.left() + active_width
        handle_rect = QRectF(handle_x - handle_radius, groove.center().y() - handle_radius, handle_radius * 2.0, handle_radius * 2.0)
        painter.setBrush(QColor(0, 0, 0, 44 if self.isEnabled() else 18))
        painter.drawEllipse(handle_rect.translated(0.0, 1.0))
        handle = QColor("#F5F2F7")
        if not self.isEnabled():
            handle.setAlpha(112)
        painter.setBrush(handle)
        painter.drawEllipse(handle_rect)
        if self._focused:
            ring = QColor(accent)
            ring.setAlpha(80)
            painter.setPen(ring)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(handle_rect.adjusted(-2.0, -2.0, 2.0, 2.0))
        painter.end()

    def _retarget(self) -> None:
        scale = 1.0
        glow = 0.16
        if self._hovered:
            scale = 1.08
            glow = 0.34
        if self._pressed:
            scale = 1.14
            glow = 0.48
        if self._focused:
            glow = max(glow, 0.42)
        if not self.isEnabled():
            scale = 0.94
            glow = 0.08
        self.motion.animate_float(self, "handleScale", None, scale, TOKENS.duration_xs, "enter", key=f"{id(self)}:handle-scale")
        self.motion.animate_float(self, "fillGlow", None, glow, TOKENS.duration_sm, "settle", key=f"{id(self)}:fill-glow")


class LiquidPopoverFrame(LiquidPanelFrame):
    pass


class LiquidContextMenuFrame(LiquidPanelFrame):
    pass
