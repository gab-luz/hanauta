from __future__ import annotations

from dataclasses import dataclass
import os
from time import perf_counter
from typing import Callable

from PyQt6.QtCore import (
    QAbstractAnimation,
    QEvent,
    QObject,
    QParallelAnimationGroup,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSequentialAnimationGroup,
    QTimer,
    QVariantAnimation,
    QEasingCurve,
    Qt,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsBlurEffect,
    QGraphicsDropShadowEffect,
    QGraphicsEffect,
    QGraphicsOpacityEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class MotionTokens:
    duration_xs: int = 90
    duration_sm: int = 140
    duration_md: int = 190
    duration_lg: int = 250


TOKENS = MotionTokens()

duration_xs = TOKENS.duration_xs
duration_sm = TOKENS.duration_sm
duration_md = TOKENS.duration_md
duration_lg = TOKENS.duration_lg


def _curve(curve_type: QEasingCurve.Type, *, amplitude: float | None = None, overshoot: float | None = None, period: float | None = None) -> QEasingCurve:
    curve = QEasingCurve(curve_type)
    if amplitude is not None:
        curve.setAmplitude(amplitude)
    if overshoot is not None:
        curve.setOvershoot(overshoot)
    if period is not None:
        curve.setPeriod(period)
    return curve

def _clamp_progress(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _mix(a: float, b: float, factor: float) -> float:
    amount = _clamp_progress(factor)
    return a + (b - a) * amount


def _smoothstep(value: float) -> float:
    t = _clamp_progress(value)
    return t * t * (3.0 - 2.0 * t)


def _ease_out_cubic(value: float) -> float:
    t = 1.0 - _clamp_progress(value)
    return 1.0 - t * t * t


def _ease_in_cubic(value: float) -> float:
    t = _clamp_progress(value)
    return t * t * t


def _ease_in_out_cubic(value: float) -> float:
    t = _clamp_progress(value)
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - pow(-2.0 * t + 2.0, 3.0) / 2.0


def _soft_peak(value: float, *, peak_start: float, peak_end: float, peak_value: float) -> float:
    t = _clamp_progress(value)
    if t <= peak_start:
        return _mix(0.0, peak_value, _smoothstep(t / max(0.001, peak_start)))
    if t >= peak_end:
        return _mix(peak_value, 0.0, _smoothstep((t - peak_end) / max(0.001, 1.0 - peak_end)))
    return peak_value


def _custom_curve(func: Callable[[float], float]) -> QEasingCurve:
    curve = QEasingCurve(QEasingCurve.Type.Linear)
    curve.setCustomType(lambda progress, _func=func: _func(progress))
    return curve


def _hover_curve(progress: float) -> float:
    t = _clamp_progress(progress)
    base = _ease_out_cubic(t)
    return _mix(base, _smoothstep(t), 0.18)


def _workspace_curve(progress: float) -> float:
    t = _clamp_progress(progress)
    base = _ease_out_cubic(t)
    overshoot = _soft_peak(t, peak_start=0.72, peak_end=0.94, peak_value=0.018)
    return min(1.03, base + overshoot)


def _modal_curve(progress: float) -> float:
    t = _clamp_progress(progress)
    base = _ease_out_cubic(t)
    overshoot = _soft_peak(t, peak_start=0.76, peak_end=0.96, peak_value=0.012)
    return min(1.02, base + overshoot)


@dataclass(frozen=True)
class EasingPreset:
    name: str
    purpose: str
    curve: QEasingCurve


EASING_PRESETS: dict[str, EasingPreset] = {
    "enter": EasingPreset("enter", "General surface arrivals and opacity recovery.", _curve(QEasingCurve.Type.OutCubic)),
    "exit": EasingPreset("exit", "Quick dismissals and reversals without drag.", _curve(QEasingCurve.Type.InCubic)),
    "emphasis": EasingPreset("emphasis", "Tactile focus changes with restrained overshoot.", _curve(QEasingCurve.Type.OutBack, overshoot=0.30)),
    "settle": EasingPreset("settle", "Return-to-rest adjustments and shadow recovery.", _curve(QEasingCurve.Type.InOutCubic)),
    "workspace": EasingPreset("workspace", "Directional workspace travel with a very light settle.", _custom_curve(_workspace_curve)),
    "hover": EasingPreset("hover", "Small pointer-driven responses that feel magnetic, not springy.", _custom_curve(_hover_curve)),
    "modal": EasingPreset("modal", "Premium panel emergence with subtle tactility near rest.", _custom_curve(_modal_curve)),
}

EASINGS = {name: preset.curve for name, preset in EASING_PRESETS.items()}
EASINGS.update(
    {
        "linear": _curve(QEasingCurve.Type.Linear),
        "elastic_soft": QEasingCurve(EASING_PRESETS["modal"].curve),
    }
)

easing_enter = QEasingCurve(EASING_PRESETS["enter"].curve)
easing_exit = QEasingCurve(EASING_PRESETS["exit"].curve)
easing_emphasis = QEasingCurve(EASING_PRESETS["emphasis"].curve)
easing_elastic_soft = QEasingCurve(EASINGS["elastic_soft"])
easing_settle = QEasingCurve(EASING_PRESETS["settle"].curve)
easing_workspace = QEasingCurve(EASING_PRESETS["workspace"].curve)
easing_hover = QEasingCurve(EASING_PRESETS["hover"].curve)
easing_modal = QEasingCurve(EASING_PRESETS["modal"].curve)


@dataclass(frozen=True)
class MotionCapabilityProfile:
    name: str = "balanced"
    duration_scale: float = 1.0
    heavy_effects_enabled: bool = True
    max_heavy_effects: int = 2
    proximity_interval_ms: int = 16


@dataclass
class MotionTelemetry:
    active_animations: int = 0
    heavy_effects: int = 0
    paint_events: int = 0
    painted_pixels: int = 0
    frame_samples: int = 0
    last_frame_ms: float = 0.0
    average_frame_ms: float = 0.0


@dataclass(frozen=True)
class MotionState:
    opacity: float = 1.0
    scale: float = 1.0
    x: float = 0.0
    y: float = 0.0
    blur: float = 0.0


@dataclass(frozen=True)
class MotionPreset:
    duration: int
    easing: QEasingCurve
    target: MotionState


@dataclass(frozen=True)
class MotionRole:
    name: str
    enter: str
    exit: str
    move: str


MOTION_PRESETS: dict[str, MotionPreset] = {
    "windowsIn": MotionPreset(duration_lg, easing_modal, MotionState(opacity=1.0, scale=1.0, y=0.0, blur=0.0)),
    "windowsOut": MotionPreset(duration_md, easing_exit, MotionState(opacity=0.0, scale=0.992, y=18.0, blur=2.0)),
    "windowsMove": MotionPreset(duration_sm, easing_enter, MotionState(opacity=1.0, scale=1.0, y=0.0, blur=0.0)),
    "layersIn": MotionPreset(duration_md, easing_enter, MotionState(opacity=1.0, scale=1.0, y=0.0, blur=0.0)),
    "layersOut": MotionPreset(duration_sm, easing_exit, MotionState(opacity=0.0, scale=0.985, y=12.0, blur=1.5)),
    "fadeIn": MotionPreset(duration_sm, easing_enter, MotionState(opacity=1.0, scale=1.0, y=0.0, blur=0.0)),
    "fadeOut": MotionPreset(duration_xs, easing_exit, MotionState(opacity=0.0, scale=0.995, y=4.0, blur=0.0)),
    "workspacesIn": MotionPreset(duration_sm, easing_workspace, MotionState(opacity=1.0, scale=1.0, x=0.0, y=0.0, blur=0.0)),
    "workspacesOut": MotionPreset(duration_xs, easing_exit, MotionState(opacity=0.45, scale=0.988, x=-10.0, y=0.0, blur=0.0)),
}

ROLE_REGISTRY: dict[str, MotionRole] = {
    "panel": MotionRole("panel", "windowsIn", "windowsOut", "windowsMove"),
    "dock": MotionRole("dock", "layersIn", "layersOut", "windowsMove"),
    "launcher": MotionRole("launcher", "layersIn", "layersOut", "windowsMove"),
    "notification": MotionRole("notification", "fadeIn", "fadeOut", "windowsMove"),
    "workspace_surface": MotionRole("workspace_surface", "workspacesIn", "workspacesOut", "windowsMove"),
    "tooltip": MotionRole("tooltip", "fadeIn", "fadeOut", "windowsMove"),
    "modal": MotionRole("modal", "windowsIn", "windowsOut", "windowsMove"),
}


def motion_preset(name: str) -> MotionPreset:
    return MOTION_PRESETS.get(name, MOTION_PRESETS["layersIn"])


def motion_role(name: str) -> MotionRole:
    return ROLE_REGISTRY.get(name, ROLE_REGISTRY["panel"])


class MotionProxy(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._scale = 1.0

    @pyqtProperty(float)
    def scale(self) -> float:
        return self._scale

    @scale.setter
    def scale(self, value: float) -> None:
        self._scale = float(value)


class SurfaceTransformEffect(QGraphicsEffect):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._opacity = 1.0
        self._scale = 1.0
        self._x_offset = 0.0
        self._y_offset = 0.0
        self._last_bounds = QRectF()

    def draw(self, painter: QPainter) -> None:  # type: ignore[override]
        pixmap, offset = self.sourcePixmap()
        if pixmap.isNull():
            return
        width = float(pixmap.width())
        height = float(pixmap.height())
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setOpacity(self._opacity)
        painter.translate(
            float(offset.x()) + width / 2.0 + self._x_offset,
            float(offset.y()) + height / 2.0 + self._y_offset,
        )
        painter.scale(self._scale, self._scale)
        painter.translate(-width / 2.0, -height / 2.0)
        painter.drawPixmap(0, 0, pixmap)
        painter.restore()

    def boundingRectFor(self, rect: QRectF) -> QRectF:  # type: ignore[override]
        dw = max(0.0, rect.width() * self._scale - rect.width()) / 2.0
        dh = max(0.0, rect.height() * self._scale - rect.height()) / 2.0
        transformed = rect.adjusted(-dw, -dh, dw, dh)
        transformed.translate(self._x_offset, self._y_offset)
        return transformed.adjusted(-1.0, -1.0, 1.0, 1.0)

    def _refresh(self, *, geometry_changed: bool) -> None:
        self.update()
        if geometry_changed:
            bounds = self.boundingRectFor(self.sourceBoundingRect())
            if bounds != self._last_bounds:
                self._last_bounds = QRectF(bounds)
                self.updateBoundingRect()

    @pyqtProperty(float)
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, value: float) -> None:
        clamped = max(0.0, min(1.0, float(value)))
        if abs(clamped - self._opacity) < 0.001:
            return
        self._opacity = clamped
        self._refresh(geometry_changed=False)

    @pyqtProperty(float)
    def scale(self) -> float:
        return self._scale

    @scale.setter
    def scale(self, value: float) -> None:
        clamped = max(0.7, float(value))
        if abs(clamped - self._scale) < 0.001:
            return
        self._scale = clamped
        self._refresh(geometry_changed=True)

    @pyqtProperty(float)
    def xOffset(self) -> float:
        return self._x_offset

    @xOffset.setter
    def xOffset(self, value: float) -> None:
        updated = float(value)
        if abs(updated - self._x_offset) < 0.01:
            return
        self._x_offset = updated
        self._refresh(geometry_changed=True)

    @pyqtProperty(float)
    def yOffset(self) -> float:
        return self._y_offset

    @yOffset.setter
    def yOffset(self, value: float) -> None:
        updated = float(value)
        if abs(updated - self._y_offset) < 0.01:
            return
        self._y_offset = updated
        self._refresh(geometry_changed=True)


class MotionProfiler(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.telemetry = MotionTelemetry()
        self._last_sample = perf_counter()
        self._watched: set[int] = set()
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._sample)
        self._timer.start()

    def watch_widget(self, widget: QWidget) -> None:
        if id(widget) in self._watched:
            return
        self._watched.add(id(widget))
        widget.installEventFilter(self)

    def animation_started(self, *, heavy: bool) -> None:
        self.telemetry.active_animations += 1
        if heavy:
            self.telemetry.heavy_effects += 1

    def animation_finished(self, *, heavy: bool) -> None:
        self.telemetry.active_animations = max(0, self.telemetry.active_animations - 1)
        if heavy:
            self.telemetry.heavy_effects = max(0, self.telemetry.heavy_effects - 1)

    def eventFilter(self, watched: QObject, event) -> bool:  # type: ignore[override]
        if event.type() == QEvent.Type.Paint and isinstance(watched, QWidget):
            rect = watched.rect()
            self.telemetry.paint_events += 1
            self.telemetry.painted_pixels += max(0, rect.width() * rect.height())
        return super().eventFilter(watched, event)

    def _sample(self) -> None:
        now = perf_counter()
        elapsed_ms = max(1.0, (now - self._last_sample) * 1000.0)
        self._last_sample = now
        self.telemetry.last_frame_ms = elapsed_ms
        self.telemetry.frame_samples += 1
        previous_total = self.telemetry.average_frame_ms * max(0, self.telemetry.frame_samples - 1)
        self.telemetry.average_frame_ms = (previous_total + elapsed_ms) / max(1, self.telemetry.frame_samples)


class MotionDebugOverlay(QLabel):
    def __init__(self, profiler: MotionProfiler, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.profiler = profiler
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setObjectName("motionDebugOverlay")
        self.setStyleSheet(
            """
            QLabel#motionDebugOverlay {
                background: rgba(9, 12, 18, 0.78);
                color: rgba(238, 242, 255, 0.96);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 12px;
                padding: 8px 10px;
                font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
                font-size: 10px;
            }
            """
        )
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self.resize(210, 74)
        self._refresh()

    def attach_to_corner(self, margin: int = 12) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.move(margin, margin)
        self.raise_()

    def _refresh(self) -> None:
        telemetry = self.profiler.telemetry
        painted_mpx = telemetry.painted_pixels / 1_000_000.0
        self.setText(
            "\n".join(
                [
                    f"active: {telemetry.active_animations}  heavy: {telemetry.heavy_effects}",
                    f"paints: {telemetry.paint_events}  area: {painted_mpx:.2f} MPx",
                    f"sample: {telemetry.last_frame_ms:.1f} ms  avg: {telemetry.average_frame_ms:.1f} ms",
                ]
            )
        )
        self.adjustSize()


class MotionSurface(QWidget):
    def __init__(self, child: QWidget, *, padding: int = 18, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._child = child
        self._effect = SurfaceTransformEffect(self)
        self.setGraphicsEffect(self._effect)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(padding, padding, padding, padding)
        layout.setSpacing(0)
        layout.addWidget(child)

    @property
    def child(self) -> QWidget:
        return self._child

    @property
    def effect(self) -> SurfaceTransformEffect:
        return self._effect

    @classmethod
    def wrap(cls, child: QWidget, *, padding: int = 18) -> MotionSurface:
        return cls(child, padding=padding)


class MotionHandle(QObject):
    def __init__(self, key: str, target: QObject, system: MotionSystem, role: str | None = None) -> None:
        super().__init__(system)
        self.key = key
        self.target = target
        self.system = system
        self.role = role

    def state(self) -> MotionState:
        effect = self.system._surface_effect(self.target)
        return MotionState(
            opacity=effect.opacity,
            scale=effect.scale,
            x=effect.xOffset,
            y=effect.yOffset,
        )

    def snap_to(self, preset_name: str) -> None:
        preset = motion_preset(preset_name)
        effect = self.system._surface_effect(self.target)
        effect.opacity = preset.target.opacity
        effect.scale = preset.target.scale
        effect.xOffset = preset.target.x
        effect.yOffset = preset.target.y

    def animate(self, preset_name: str, *, delay: int = 0, duration: int | None = None) -> QParallelAnimationGroup:
        return self.system.animate_surface(self.key, self.target, preset_name, delay=delay, duration=duration)

    def animate_role(self, phase: str, *, delay: int = 0, duration: int | None = None) -> QParallelAnimationGroup | None:
        if self.role is None:
            return None
        role = motion_role(self.role)
        preset_name = {
            "enter": role.enter,
            "exit": role.exit,
            "move": role.move,
        }.get(phase)
        if preset_name is None:
            return None
        return self.animate(preset_name, delay=delay, duration=duration)


class MotionSystem(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.tokens = TOKENS
        self.easings = {name: QEasingCurve(curve) for name, curve in EASINGS.items()}
        self.presets = dict(MOTION_PRESETS)
        self.roles = dict(ROLE_REGISTRY)
        self.capability = self._detect_capability()
        self.profiler = MotionProfiler(self)
        self._running: dict[str, QAbstractAnimation] = {}
        self._animation_heavy: dict[str, bool] = {}
        self._delayed: dict[str, QTimer] = {}
        self._handles: dict[str, MotionHandle] = {}

    def create_debug_overlay(self, parent: QWidget) -> MotionDebugOverlay:
        self.profiler.watch_widget(parent)
        overlay = MotionDebugOverlay(self.profiler, parent)
        overlay.attach_to_corner()
        overlay.show()
        return overlay

    def easing(self, name: str | QEasingCurve | None) -> QEasingCurve:
        if isinstance(name, QEasingCurve):
            return QEasingCurve(name)
        if name is None:
            return QEasingCurve(self.easings["enter"])
        return QEasingCurve(self.easings.get(name, self.easings["enter"]))

    def register(self, key: str, target: QObject, *, role: str | None = None, initial_preset: str | None = None) -> MotionHandle:
        handle = MotionHandle(key, target, self, role=role)
        if initial_preset is not None:
            handle.snap_to(initial_preset)
        self._handles[key] = handle
        return handle

    def controller(self, key: str) -> MotionHandle | None:
        return self._handles.get(key)

    def register_role(self, key: str, role: str, target: QObject, *, initial_phase: str | None = None) -> MotionHandle:
        handle = self.register(key, target, role=role)
        if initial_phase is not None:
            handle.animate_role(initial_phase)
        return handle

    def cancel(self, key: str) -> None:
        delayed = self._delayed.pop(key, None)
        if delayed is not None:
            delayed.stop()
            delayed.deleteLater()
        animation = self._running.pop(key, None)
        if animation is None:
            return
        heavy = self._animation_heavy.pop(key, False)
        self.profiler.animation_finished(heavy=heavy)
        animation.stop()
        animation.deleteLater()

    def stagger(self, keys: list[str], preset_name: str, *, step_ms: int = 26) -> None:
        for index, key in enumerate(keys):
            handle = self._handles.get(key)
            if handle is None:
                continue
            handle.animate(preset_name, delay=index * step_ms)

    def play(self, key: str, preset_name: str, *, delay: int = 0, duration: int | None = None) -> QParallelAnimationGroup | None:
        handle = self._handles.get(key)
        if handle is None:
            return None
        return handle.animate(preset_name, delay=delay, duration=duration)

    def animate_opacity(
        self,
        widget: QWidget,
        from_value: float | None,
        to_value: float,
        duration: int,
        easing: str | QEasingCurve | None = None,
        *,
        key: str | None = None,
    ) -> QPropertyAnimation:
        effect = self._ensure_opacity_effect(widget)
        start_value = effect.opacity() if from_value is None else from_value
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setStartValue(start_value)
        animation.setEndValue(to_value)
        animation.setDuration(self._duration(duration))
        animation.setEasingCurve(self.easing(easing))
        return self._start_animation(key or self._animation_key(widget, "opacity"), animation)

    def animate_geometry(
        self,
        widget: QWidget,
        start_rect: QRect | None,
        end_rect: QRect,
        duration: int,
        easing: str | QEasingCurve | None = None,
        *,
        key: str | None = None,
    ) -> QPropertyAnimation:
        animation = QPropertyAnimation(widget, b"geometry", self)
        animation.setStartValue(widget.geometry() if start_rect is None else start_rect)
        animation.setEndValue(end_rect)
        animation.setDuration(self._duration(duration))
        animation.setEasingCurve(self.easing(easing))
        return self._start_animation(key or self._animation_key(widget, "geometry"), animation)

    def animate_scale(
        self,
        proxy_object: QObject,
        from_value: float | None,
        to_value: float,
        duration: int,
        easing: str | QEasingCurve | None = None,
        *,
        key: str | None = None,
    ) -> QPropertyAnimation:
        animation = QPropertyAnimation(proxy_object, b"scale", self)
        start_value = getattr(proxy_object, "scale", None)
        if callable(start_value):
            current = float(start_value())
        else:
            current = float(start_value if start_value is not None else 1.0)
        animation.setStartValue(current if from_value is None else from_value)
        animation.setEndValue(to_value)
        animation.setDuration(self._duration(duration))
        animation.setEasingCurve(self.easing(easing))
        return self._start_animation(key or self._animation_key(proxy_object, "scale"), animation)

    def animate_blur(
        self,
        effect: QGraphicsBlurEffect | QGraphicsDropShadowEffect,
        from_value: float | None,
        to_value: float,
        duration: int,
        easing: str | QEasingCurve | None = None,
        *,
        key: str | None = None,
    ) -> QPropertyAnimation:
        if not self.can_run_heavy_effect():
            effect.setBlurRadius(to_value)
            animation = QPropertyAnimation(effect, b"blurRadius", self)
            animation.setDuration(1)
            animation.setStartValue(effect.blurRadius())
            animation.setEndValue(effect.blurRadius())
            return self._start_animation(key or self._animation_key(effect, "blurRadius"), animation, heavy=False)
        animation = QPropertyAnimation(effect, b"blurRadius", self)
        current = float(effect.blurRadius())
        animation.setStartValue(current if from_value is None else from_value)
        animation.setEndValue(to_value)
        animation.setDuration(self._duration(duration))
        animation.setEasingCurve(self.easing(easing))
        return self._start_animation(key or self._animation_key(effect, "blurRadius"), animation, heavy=True)

    def animate_float(
        self,
        target: QObject,
        property_name: str | bytes,
        from_value: float | None,
        to_value: float,
        duration: int,
        easing: str | QEasingCurve | None = None,
        *,
        key: str | None = None,
    ) -> QPropertyAnimation:
        property_key = property_name.decode() if isinstance(property_name, bytes) else property_name
        animation = QPropertyAnimation(target, property_key.encode("utf-8"), self)
        current_value = target.property(property_key)
        try:
            current = float(current_value)
        except (TypeError, ValueError):
            current = to_value if from_value is None else from_value
        animation.setStartValue(current if from_value is None else from_value)
        animation.setEndValue(to_value)
        animation.setDuration(self._duration(duration))
        animation.setEasingCurve(self.easing(easing))
        return self._start_animation(key or self._animation_key(target, property_key), animation)

    def animate_value(
        self,
        key: str,
        from_value: float,
        to_value: float,
        duration: int,
        easing: str | QEasingCurve | None,
        on_value: Callable[[float], None],
    ) -> QVariantAnimation:
        animation = QVariantAnimation(self)
        animation.setStartValue(from_value)
        animation.setEndValue(to_value)
        animation.setDuration(self._duration(duration))
        animation.setEasingCurve(self.easing(easing))
        animation.valueChanged.connect(lambda value: on_value(float(value)))
        return self._start_animation(key, animation)

    def parallel(self, key: str, animations: list[QAbstractAnimation]) -> QParallelAnimationGroup:
        self.cancel(key)
        group = QParallelAnimationGroup(self)
        for animation in animations:
            group.addAnimation(animation)
        self._register_running(key, group, heavy=self._animations_are_heavy(animations))
        group.start()
        return group

    def sequence(self, key: str, animations: list[QAbstractAnimation]) -> QSequentialAnimationGroup:
        self.cancel(key)
        group = QSequentialAnimationGroup(self)
        for animation in animations:
            group.addAnimation(animation)
        self._register_running(key, group, heavy=self._animations_are_heavy(animations))
        group.start()
        return group

    def animate_surface(
        self,
        key: str,
        target: QObject,
        preset_name: str,
        *,
        delay: int = 0,
        duration: int | None = None,
    ) -> QParallelAnimationGroup:
        if delay > 0:
            self.cancel(key)
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self.animate_surface(key, target, preset_name, duration=duration))
            self._delayed[key] = timer
            timer.start(self._duration(delay))
            return QParallelAnimationGroup(self)
        preset = motion_preset(preset_name)
        effect = self._surface_effect(target)
        animations = [
            self._make_property_animation(effect, b"opacity", effect.opacity, preset.target.opacity, duration or preset.duration, preset.easing),
            self._make_property_animation(effect, b"scale", effect.scale, preset.target.scale, duration or preset.duration, preset.easing),
            self._make_property_animation(effect, b"xOffset", effect.xOffset, preset.target.x, duration or preset.duration, preset.easing),
            self._make_property_animation(effect, b"yOffset", effect.yOffset, preset.target.y, duration or preset.duration, preset.easing),
        ]
        animations = [animation for animation in animations if animation is not None]
        if not animations:
            group = QParallelAnimationGroup(self)
            return group
        return self.parallel(key, animations)

    def _surface_effect(self, target: QObject) -> SurfaceTransformEffect:
        if isinstance(target, MotionSurface):
            return target.effect
        if isinstance(target, QWidget):
            effect = target.graphicsEffect()
            if isinstance(effect, SurfaceTransformEffect):
                return effect
            if effect is not None:
                raise RuntimeError("Motion surface target already has a graphics effect")
            created = SurfaceTransformEffect(target)
            target.setGraphicsEffect(created)
            return created
        raise TypeError("Surface animations require a QWidget or MotionSurface")

    def _ensure_opacity_effect(self, widget: QWidget) -> QGraphicsOpacityEffect:
        effect = widget.graphicsEffect()
        if isinstance(effect, QGraphicsOpacityEffect):
            return effect
        if effect is not None:
            raise RuntimeError("Opacity animation requires an unoccupied graphics effect slot")
        created = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(created)
        return created

    def _make_property_animation(
        self,
        target: QObject,
        prop: bytes,
        current_getter: Callable[[], float] | float,
        end_value: float,
        duration: int,
        easing: QEasingCurve,
    ) -> QPropertyAnimation | None:
        current = float(current_getter() if callable(current_getter) else current_getter)
        if abs(current - end_value) < 0.001:
            return None
        animation = QPropertyAnimation(target, prop, self)
        animation.setStartValue(current)
        animation.setEndValue(end_value)
        animation.setDuration(self._duration(duration))
        animation.setEasingCurve(QEasingCurve(easing))
        return animation

    def _animation_key(self, target: QObject, property_name: str) -> str:
        return f"{id(target)}:{property_name}"

    def _register_running(self, key: str, animation: QAbstractAnimation, *, heavy: bool = False) -> None:
        self._running[key] = animation
        self._animation_heavy[key] = heavy
        self.profiler.animation_started(heavy=heavy)
        animation.finished.connect(lambda key=key: self._finalize_animation(key))

    def _finalize_animation(self, key: str) -> None:
        animation = self._running.pop(key, None)
        if animation is None:
            return
        heavy = self._animation_heavy.pop(key, False)
        self.profiler.animation_finished(heavy=heavy)
        animation.deleteLater()

    def _start_animation(
        self,
        key: str,
        animation: QPropertyAnimation | QVariantAnimation,
        *,
        heavy: bool = False,
    ) -> QPropertyAnimation | QVariantAnimation:
        self.cancel(key)
        self._register_running(key, animation, heavy=heavy)
        animation.start()
        return animation

    def can_run_heavy_effect(self) -> bool:
        return self.capability.heavy_effects_enabled and self.profiler.telemetry.heavy_effects < self.capability.max_heavy_effects

    def _duration(self, duration: int) -> int:
        return max(1, int(duration * self.capability.duration_scale))

    def _animations_are_heavy(self, animations: list[QAbstractAnimation]) -> bool:
        for animation in animations:
            prop_name = bytes(animation.propertyName()).decode("utf-8") if isinstance(animation, QPropertyAnimation) else ""
            if prop_name == "blurRadius":
                return True
        return False

    def _detect_capability(self) -> MotionCapabilityProfile:
        forced = os.environ.get("HANAUTA_MOTION_QUALITY", "").strip().lower()
        if forced == "low":
            return MotionCapabilityProfile(name="low", duration_scale=0.92, heavy_effects_enabled=False, max_heavy_effects=0, proximity_interval_ms=28)
        if forced == "high":
            return MotionCapabilityProfile(name="high", duration_scale=1.0, heavy_effects_enabled=True, max_heavy_effects=3, proximity_interval_ms=16)
        cpu_count = os.cpu_count() or 4
        screen = QApplication.primaryScreen()
        pixels = 0
        if screen is not None:
            geometry = screen.availableGeometry()
            dpr = screen.devicePixelRatio()
            pixels = int(geometry.width() * geometry.height() * max(1.0, dpr))
        if cpu_count <= 4 or pixels >= 4_500_000:
            return MotionCapabilityProfile(name="balanced-low", duration_scale=0.96, heavy_effects_enabled=False, max_heavy_effects=0, proximity_interval_ms=24)
        return MotionCapabilityProfile()


class MotionDirector(MotionSystem):
    pass


class ReactiveMotion(QObject):
    def __init__(
        self,
        widget: QWidget,
        color: str | QColor,
        *,
        base_alpha: float = 0.0,
        hover_alpha: float = 0.2,
        press_alpha: float = 0.12,
        base_blur: float = 0.0,
        hover_blur: float = 18.0,
        press_blur: float = 10.0,
        base_offset: float = 0.0,
        hover_offset: float = 8.0,
        press_offset: float = 3.0,
        duration: int = duration_xs,
        easing: QEasingCurve = easing_enter,
    ) -> None:
        super().__init__(widget)
        self.widget = widget
        self._duration = max(40, int(duration))
        self._easing = QEasingCurve(easing)
        self._base_alpha = max(0.0, min(1.0, base_alpha))
        self._hover_alpha = max(0.0, min(1.0, hover_alpha))
        self._press_alpha = max(0.0, min(1.0, press_alpha))
        self._base_blur = max(0.0, float(base_blur))
        self._hover_blur = max(0.0, float(hover_blur))
        self._press_blur = max(0.0, float(press_blur))
        self._base_offset = float(base_offset)
        self._hover_offset = float(hover_offset)
        self._press_offset = float(press_offset)
        self._pressed = False
        self._hovered = False
        self._base_color = QColor(color)
        self._group: QParallelAnimationGroup | None = None

        self.effect = QGraphicsDropShadowEffect(widget)
        self.effect.setBlurRadius(self._base_blur)
        self.effect.setOffset(QPointF(0.0, self._base_offset))
        self.effect.setColor(self._shadow_color(self._base_alpha))
        widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        widget.setGraphicsEffect(self.effect)
        widget.installEventFilter(self)

    def set_color(self, color: str | QColor) -> None:
        self._base_color = QColor(color)
        self._animate_to_current(immediate=True)

    def eventFilter(self, watched: QObject, event) -> bool:  # type: ignore[override]
        if watched is not self.widget:
            return super().eventFilter(watched, event)
        event_type = event.type()
        if event_type == QEvent.Type.Enter:
            self._hovered = True
            self._animate_to_current()
        elif event_type == QEvent.Type.Leave:
            self._hovered = False
            self._pressed = False
            self._animate_to_current()
        elif event_type == QEvent.Type.MouseButtonPress:
            self._pressed = True
            self._animate_to_current()
        elif event_type == QEvent.Type.MouseButtonRelease:
            self._pressed = False
            self._animate_to_current()
        return super().eventFilter(watched, event)

    def _shadow_color(self, alpha: float) -> QColor:
        color = QColor(self._base_color)
        color.setAlphaF(max(0.0, min(1.0, alpha)))
        return color

    def _targets(self) -> tuple[float, float, QColor]:
        if self._pressed:
            return self._press_blur, self._press_offset, self._shadow_color(self._press_alpha)
        if self._hovered:
            return self._hover_blur, self._hover_offset, self._shadow_color(self._hover_alpha)
        return self._base_blur, self._base_offset, self._shadow_color(self._base_alpha)

    def _animate_to_current(self, *, immediate: bool = False) -> None:
        blur, offset, color = self._targets()
        if self._group is not None:
            self._group.stop()
            self._group.deleteLater()
            self._group = None
        if immediate:
            self.effect.setBlurRadius(blur)
            self.effect.setOffset(QPointF(0.0, offset))
            self.effect.setColor(color)
            return
        self._group = QParallelAnimationGroup(self)

        blur_animation = QPropertyAnimation(self.effect, b"blurRadius", self._group)
        blur_animation.setStartValue(self.effect.blurRadius())
        blur_animation.setEndValue(blur)
        blur_animation.setDuration(self._duration)
        blur_animation.setEasingCurve(QEasingCurve(self._easing))
        self._group.addAnimation(blur_animation)

        offset_animation = QPropertyAnimation(self.effect, b"yOffset", self._group)
        offset_animation.setStartValue(float(self.effect.yOffset()))
        offset_animation.setEndValue(offset)
        offset_animation.setDuration(self._duration)
        offset_animation.setEasingCurve(QEasingCurve(self._easing))
        self._group.addAnimation(offset_animation)

        color_animation = QVariantAnimation(self._group)
        color_animation.setStartValue(self.effect.color().alphaF())
        color_animation.setEndValue(color.alphaF())
        color_animation.setDuration(self._duration)
        color_animation.setEasingCurve(QEasingCurve(self._easing))
        color_animation.valueChanged.connect(
            lambda value: self.effect.setColor(self._shadow_color(float(value)))
        )
        self._group.addAnimation(color_animation)
        self._group.start()


def attach_reactive_motion(widget: QWidget, color: str | QColor, **kwargs) -> ReactiveMotion | None:
    current = getattr(widget, "_reactive_motion", None)
    if isinstance(current, ReactiveMotion):
        current.set_color(color)
        return current
    if widget.graphicsEffect() is not None:
        return None
    motion = ReactiveMotion(widget, color, **kwargs)
    setattr(widget, "_reactive_motion", motion)
    return motion
