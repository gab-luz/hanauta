from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QRect,
    QSize,
    Qt,
    QParallelAnimationGroup,
    QPauseAnimation,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    QEasingCurve,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsBlurEffect,
    QStackedWidget,
    QWidget,
)

from pyqt.shared.motion import MotionSystem, MotionTokens, easing_enter, easing_exit, easing_settle, easing_workspace


@dataclass(frozen=True)
class WorkspaceTransitionTuning:
    motion_percent: float = 0.14
    outgoing_drift_factor: float = 0.22
    outgoing_opacity: float = 0.58
    outgoing_scale: float = 0.987
    outgoing_dim: float = 0.18
    outgoing_blur: float = 1.6
    incoming_opacity_start: float = 0.72
    incoming_scale_start: float = 0.986
    incoming_overshoot_px: float = 4.0
    incoming_overshoot_scale: float = 1.003
    settle_pause_ms: int = 12
    duration_main: int = MotionTokens().duration_md
    duration_settle: int = 70


class WorkspaceSnapshotLayer(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap()
        self._opacity = 1.0
        self._scale = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._dim_opacity = 0.0
        self._dim_color = QColor(8, 10, 14)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setVisible(False)
        self._blur = QGraphicsBlurEffect(self)
        self._blur.setBlurHints(QGraphicsBlurEffect.BlurHint.PerformanceHint)
        self._blur.setBlurRadius(0.0)
        self.setGraphicsEffect(self._blur)

    def set_snapshot(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.setVisible(not pixmap.isNull())
        self.update()

    def blur_effect(self) -> QGraphicsBlurEffect:
        return self._blur

    @pyqtProperty(float)
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, value: float) -> None:
        self._opacity = max(0.0, min(1.0, float(value)))
        self.update()

    @pyqtProperty(float)
    def scale(self) -> float:
        return self._scale

    @scale.setter
    def scale(self, value: float) -> None:
        self._scale = max(0.85, float(value))
        self.update()

    @pyqtProperty(float)
    def offsetX(self) -> float:
        return self._offset_x

    @offsetX.setter
    def offsetX(self, value: float) -> None:
        self._offset_x = float(value)
        self.update()

    @pyqtProperty(float)
    def offsetY(self) -> float:
        return self._offset_y

    @offsetY.setter
    def offsetY(self, value: float) -> None:
        self._offset_y = float(value)
        self.update()

    @pyqtProperty(float)
    def dimOpacity(self) -> float:
        return self._dim_opacity

    @dimOpacity.setter
    def dimOpacity(self, value: float) -> None:
        self._dim_opacity = max(0.0, min(1.0, float(value)))
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setOpacity(self._opacity)
        width = float(self._pixmap.width())
        height = float(self._pixmap.height())
        center_x = self.width() / 2.0 + self._offset_x
        center_y = self.height() / 2.0 + self._offset_y
        painter.translate(center_x, center_y)
        painter.scale(self._scale, self._scale)
        painter.translate(-width / 2.0, -height / 2.0)
        painter.drawPixmap(0, 0, self._pixmap)
        if self._dim_opacity > 0.0:
            dim = QColor(self._dim_color)
            dim.setAlphaF(self._dim_opacity)
            painter.fillRect(QRect(0, 0, int(width), int(height)), dim)
        painter.end()


class WorkspaceTransitionOverlay(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.outgoing_layer = WorkspaceSnapshotLayer(self)
        self.incoming_layer = WorkspaceSnapshotLayer(self)
        self.hide()

    def sync_to_parent(self) -> None:
        self.setGeometry(self.parentWidget().rect())
        self.outgoing_layer.setGeometry(self.rect())
        self.incoming_layer.setGeometry(self.rect())

    def clear(self) -> None:
        self.outgoing_layer.set_snapshot(QPixmap())
        self.incoming_layer.set_snapshot(QPixmap())
        self.hide()


class WorkspaceTransitionController(QObject):
    def __init__(
        self,
        stack: QStackedWidget,
        *,
        motion: MotionSystem | None = None,
        tuning: WorkspaceTransitionTuning | None = None,
    ) -> None:
        super().__init__(stack)
        self.stack = stack
        self.motion = motion or MotionSystem(self)
        self.tuning = tuning or WorkspaceTransitionTuning()
        self.overlay = WorkspaceTransitionOverlay(stack)
        self.overlay.sync_to_parent()
        self.stack.installEventFilter(self)
        self._active_animation: QSequentialAnimationGroup | None = None
        self._current_index = stack.currentIndex()
        self._target_index = self._current_index
        self._snapshot_cache: dict[tuple[int, int, int], QPixmap] = {}
        self._last_composite_snapshot = QPixmap()

    def eventFilter(self, watched: QObject, event) -> bool:  # type: ignore[override]
        if watched is self.stack and event.type() in {QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.Move}:
            self.overlay.sync_to_parent()
            self._snapshot_cache.clear()
            self._last_composite_snapshot = QPixmap()
        return super().eventFilter(watched, event)

    def set_motion_percent(self, percent: float) -> None:
        self.tuning = WorkspaceTransitionTuning(
            motion_percent=max(0.04, min(0.35, float(percent))),
            outgoing_drift_factor=self.tuning.outgoing_drift_factor,
            outgoing_opacity=self.tuning.outgoing_opacity,
            outgoing_scale=self.tuning.outgoing_scale,
            outgoing_dim=self.tuning.outgoing_dim,
            outgoing_blur=self.tuning.outgoing_blur,
            incoming_opacity_start=self.tuning.incoming_opacity_start,
            incoming_scale_start=self.tuning.incoming_scale_start,
            incoming_overshoot_px=self.tuning.incoming_overshoot_px,
            incoming_overshoot_scale=self.tuning.incoming_overshoot_scale,
            settle_pause_ms=self.tuning.settle_pause_ms,
            duration_main=self.tuning.duration_main,
            duration_settle=self.tuning.duration_settle,
        )

    def switch_to(self, index: int, *, direction: int | None = None) -> None:
        if index < 0 or index >= self.stack.count():
            return
        current_index = self._target_index if self._active_animation is not None else self.stack.currentIndex()
        if index == current_index and self._active_animation is None:
            return

        resolved_direction = direction
        if resolved_direction is None:
            if index > current_index:
                resolved_direction = 1
            elif index < current_index:
                resolved_direction = -1
            else:
                resolved_direction = 1

        outgoing_snapshot = self._current_visual_snapshot(current_index)
        self._stop_active_transition()

        self._target_index = index
        incoming_snapshot = self._snapshot_widget(self.stack.widget(index), cache_key=index)
        self.stack.setCurrentIndex(index)

        self.overlay.sync_to_parent()
        self.overlay.outgoing_layer.set_snapshot(outgoing_snapshot)
        self.overlay.incoming_layer.set_snapshot(incoming_snapshot)
        self.overlay.show()
        self.overlay.raise_()

        self._prepare_layers(resolved_direction)
        self._active_animation = self._build_transition(index, resolved_direction)
        self._active_animation.finished.connect(lambda target=index: self._finish_transition(target))
        self._active_animation.start()

    def invalidate_snapshot(self, index: int | None = None) -> None:
        self._last_composite_snapshot = QPixmap()
        if index is None:
            self._snapshot_cache.clear()
            return
        for key in list(self._snapshot_cache.keys()):
            if key[0] == index:
                self._snapshot_cache.pop(key, None)

    def _prepare_layers(self, direction: int) -> None:
        outgoing_blur = self._effective_outgoing_blur()
        travel = self._travel_distance()
        self.overlay.outgoing_layer.opacity = 1.0
        self.overlay.outgoing_layer.scale = 1.0
        self.overlay.outgoing_layer.offsetX = 0.0
        self.overlay.outgoing_layer.offsetY = 0.0
        self.overlay.outgoing_layer.dimOpacity = 0.0
        self.overlay.outgoing_layer.blur_effect().setBlurRadius(0.0)

        self.overlay.incoming_layer.opacity = self.tuning.incoming_opacity_start
        self.overlay.incoming_layer.scale = self.tuning.incoming_scale_start
        self.overlay.incoming_layer.offsetX = float(direction * travel)
        self.overlay.incoming_layer.offsetY = 0.0
        self.overlay.incoming_layer.dimOpacity = 0.0
        self.overlay.incoming_layer.blur_effect().setBlurRadius(0.0)
        if outgoing_blur <= 0.0:
            self.overlay.outgoing_layer.blur_effect().setEnabled(False)
        else:
            self.overlay.outgoing_layer.blur_effect().setEnabled(True)

    def _build_transition(self, index: int, direction: int) -> QSequentialAnimationGroup:
        main = QParallelAnimationGroup(self)
        settle = QParallelAnimationGroup(self)
        sequence = QSequentialAnimationGroup(self)
        travel = self._travel_distance()
        outgoing_blur = self._effective_outgoing_blur()
        outgoing_target_x = float(-direction * travel * self.tuning.outgoing_drift_factor)
        incoming_mid_x = float(direction * self.tuning.incoming_overshoot_px)

        main.addAnimation(self._float_animation(self.overlay.outgoing_layer, b"offsetX", outgoing_target_x, self.tuning.duration_main, easing_exit))
        main.addAnimation(self._float_animation(self.overlay.outgoing_layer, b"opacity", self.tuning.outgoing_opacity, self.tuning.duration_main, easing_exit))
        main.addAnimation(self._float_animation(self.overlay.outgoing_layer, b"scale", self.tuning.outgoing_scale, self.tuning.duration_main, easing_exit))
        main.addAnimation(self._float_animation(self.overlay.outgoing_layer, b"dimOpacity", self.tuning.outgoing_dim, self.tuning.duration_main, easing_exit))
        if outgoing_blur > 0.0:
            main.addAnimation(self._blur_animation(
                self.overlay.outgoing_layer.blur_effect(),
                outgoing_blur,
                self.tuning.duration_main,
                easing_exit,
            ))

        incoming_group = QParallelAnimationGroup(main)
        incoming_group.addAnimation(self._float_animation(self.overlay.incoming_layer, b"offsetX", incoming_mid_x, self.tuning.duration_main, easing_workspace))
        incoming_group.addAnimation(self._float_animation(self.overlay.incoming_layer, b"opacity", 1.0, self.tuning.duration_main, easing_workspace))
        incoming_group.addAnimation(self._float_animation(self.overlay.incoming_layer, b"scale", self.tuning.incoming_overshoot_scale, self.tuning.duration_main, easing_workspace))
        main.addAnimation(incoming_group)

        if self.tuning.settle_pause_ms > 0:
            sequence.addAnimation(QPauseAnimation(self.tuning.settle_pause_ms))
        sequence.addAnimation(main)

        settle.addAnimation(self._float_animation(self.overlay.incoming_layer, b"offsetX", 0.0, self.tuning.duration_settle, easing_settle))
        settle.addAnimation(self._float_animation(self.overlay.incoming_layer, b"scale", 1.0, self.tuning.duration_settle, easing_settle))
        if outgoing_blur > 0.0:
            settle.addAnimation(self._blur_animation(
                self.overlay.outgoing_layer.blur_effect(),
                0.0,
                self.tuning.duration_settle,
                easing_enter,
            ))
        sequence.addAnimation(settle)
        return sequence

    def _float_animation(
        self,
        target: QObject,
        property_name: bytes,
        end_value: float,
        duration: int,
        easing: QEasingCurve,
    ) -> QPropertyAnimation:
        animation = QPropertyAnimation(target, property_name, self)
        current_value = float(target.property(property_name.decode("utf-8")))
        animation.setStartValue(current_value)
        animation.setEndValue(end_value)
        animation.setDuration(max(1, int(duration)))
        animation.setEasingCurve(QEasingCurve(easing))
        return animation

    def _blur_animation(
        self,
        effect: QGraphicsBlurEffect,
        end_value: float,
        duration: int,
        easing: QEasingCurve,
    ) -> QPropertyAnimation:
        animation = QPropertyAnimation(effect, b"blurRadius", self)
        animation.setStartValue(effect.blurRadius())
        animation.setEndValue(end_value)
        animation.setDuration(max(1, int(duration)))
        animation.setEasingCurve(QEasingCurve(easing))
        return animation

    def _travel_distance(self) -> int:
        return max(24, int(self.stack.width() * self.tuning.motion_percent))

    def _finish_transition(self, index: int) -> None:
        self._current_index = index
        self._target_index = index
        self._active_animation = None
        self._last_composite_snapshot = self._snapshot_widget(self.stack.widget(index), cache_key=index)
        self.overlay.clear()

    def _stop_active_transition(self) -> None:
        if self._active_animation is None:
            return
        self._active_animation.stop()
        self._active_animation.deleteLater()
        self._active_animation = None

    def _current_visual_snapshot(self, fallback_index: int) -> QPixmap:
        if not self._last_composite_snapshot.isNull():
            return self._last_composite_snapshot
        if self.overlay.isVisible():
            composite = QPixmap(self.overlay.size() * self.overlay.devicePixelRatioF())
            composite.setDevicePixelRatio(self.overlay.devicePixelRatioF())
            composite.fill(Qt.GlobalColor.transparent)
            self.overlay.render(composite, QPoint(), self.overlay.rect())
            self._last_composite_snapshot = composite
            return composite
        return self._snapshot_widget(self.stack.widget(fallback_index), cache_key=fallback_index)

    def _snapshot_widget(self, widget: QWidget | None, *, cache_key: int | None = None) -> QPixmap:
        if widget is None:
            return QPixmap()
        size = widget.size()
        if size.isEmpty():
            size = self.stack.size()
        dpr = self.stack.devicePixelRatioF()
        cache_token = None
        if cache_key is not None:
            cache_token = (cache_key, size.width(), size.height())
            cached = self._snapshot_cache.get(cache_token)
            if cached is not None and not cached.isNull():
                return cached
        pixmap = QPixmap(int(size.width() * dpr), int(size.height() * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        widget.render(pixmap, QPoint(), QRect(QPoint(0, 0), size))
        if cache_token is not None:
            self._snapshot_cache[cache_token] = pixmap
        return pixmap

    def _effective_outgoing_blur(self) -> float:
        if not self.motion.can_run_heavy_effect():
            return 0.0
        return self.tuning.outgoing_blur
