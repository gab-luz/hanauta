from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import (
    QEvent,
    QObject,
    QPointF,
    QRect,
    Qt,
    QParallelAnimationGroup,
    QPropertyAnimation,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QKeyEvent, QPainter, QPainterPath, QPixmap, QRadialGradient
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pyqt.shared.motion import MotionSystem, SurfaceTransformEffect, TOKENS


@dataclass(frozen=True)
class ModalAction:
    key: str
    label: str
    primary: bool = False


@dataclass(frozen=True)
class ModalPayload:
    title: str
    body: str = ""
    kind: str = "notification"
    subtitle: str = ""
    dismiss_label: str = "Dismiss"
    actions: tuple[ModalAction, ...] = ()
    icon_text: str = ""
    icon_pixmap: QPixmap | None = None
    allow_escape: bool = True
    auto_dismiss_ms: int = 0
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ModalMotionSpec:
    backdrop_opacity: float = 0.26
    enter_scale_start: float = 0.96
    enter_offset_y: float = 18.0
    exit_scale_end: float = 0.985
    exit_offset_y: float = -10.0
    halo_opacity: float = 0.62
    halo_blur_start: float = 18.0
    halo_blur_end: float = 7.0
    shadow_blur_rest: float = 34.0
    shadow_blur_soft: float = 22.0
    shadow_alpha_rest: float = 0.34
    shadow_alpha_soft: float = 0.18
    shadow_offset_rest: float = 22.0
    shadow_offset_soft: float = 12.0
    duration_in: int = TOKENS.duration_md + 40
    duration_out: int = TOKENS.duration_sm


@dataclass(frozen=True)
class ModalLayoutSpec:
    min_width: int = 360
    max_width: int = 460
    screen_margin: int = 36
    shell_padding: int = 28
    card_radius: int = 26
    halo_margin_x: int = 34
    halo_margin_y: int = 28


class ModalStackPolicy:
    REPLACE = "replace"
    QUEUE = "queue"
    STACK = "stack"


class BackdropLayer(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._opacity = 0.0
        self._tint = QColor(7, 10, 16)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    @pyqtProperty(float)
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, value: float) -> None:
        self._opacity = max(0.0, min(1.0, float(value)))
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if self._opacity <= 0.0:
            return
        painter = QPainter(self)
        color = QColor(self._tint)
        color.setAlphaF(self._opacity)
        painter.fillRect(self.rect(), color)
        painter.end()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class HaloLayer(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._opacity = 0.0
        self._blur_radius = 0.0
        self._center_color = QColor(255, 255, 255, 84)
        self._edge_color = QColor(255, 255, 255, 0)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    @pyqtProperty(float)
    def opacity(self) -> float:
        return self._opacity

    @opacity.setter
    def opacity(self, value: float) -> None:
        self._opacity = max(0.0, min(1.0, float(value)))
        self.update()

    @pyqtProperty(float)
    def blurRadius(self) -> float:
        return self._blur_radius

    @blurRadius.setter
    def blurRadius(self, value: float) -> None:
        self._blur_radius = max(0.0, float(value))
        self.update()

    def set_colors(self, center: str | QColor, edge: str | QColor) -> None:
        self._center_color = QColor(center)
        self._edge_color = QColor(edge)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if self._opacity <= 0.0 or self.width() <= 0 or self.height() <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        blur_factor = min(1.0, self._blur_radius / 24.0)
        rect = self.rect().adjusted(4, 4, -4, -4)
        gradient = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * (0.54 + blur_factor * 0.12))
        center = QColor(self._center_color)
        edge = QColor(self._edge_color)
        center.setAlphaF(center.alphaF() * self._opacity * (0.92 - blur_factor * 0.22))
        edge.setAlphaF(edge.alphaF() * self._opacity)
        gradient.setColorAt(0.0, center)
        gradient.setColorAt(0.72, QColor(center.red(), center.green(), center.blue(), int(center.alpha() * 0.26)))
        gradient.setColorAt(1.0, edge)
        path = QPainterPath()
        path.addRoundedRect(rect, 36.0 + blur_factor * 8.0, 36.0 + blur_factor * 8.0)
        painter.fillPath(path, gradient)
        painter.end()


class ShadowProxy(QObject):
    def __init__(self, effect: QGraphicsDropShadowEffect, color: QColor, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._effect = effect
        self._base_color = QColor(color)
        self._blur = effect.blurRadius()
        self._alpha = color.alphaF()
        self._y_offset = effect.offset().y()
        self._sync()

    @pyqtProperty(float)
    def blur(self) -> float:
        return self._blur

    @blur.setter
    def blur(self, value: float) -> None:
        self._blur = max(0.0, float(value))
        self._sync()

    @pyqtProperty(float)
    def alpha(self) -> float:
        return self._alpha

    @alpha.setter
    def alpha(self, value: float) -> None:
        self._alpha = max(0.0, min(1.0, float(value)))
        self._sync()

    @pyqtProperty(float)
    def yOffset(self) -> float:
        return self._y_offset

    @yOffset.setter
    def yOffset(self, value: float) -> None:
        self._y_offset = float(value)
        self._sync()

    def _sync(self) -> None:
        color = QColor(self._base_color)
        color.setAlphaF(self._alpha)
        self._effect.setColor(color)
        self._effect.setBlurRadius(self._blur)
        self._effect.setOffset(QPointF(0.0, self._y_offset))


class ModalCard(QFrame):
    actionTriggered = pyqtSignal(str)
    dismissed = pyqtSignal()

    def __init__(self, ui_font: str, icon_font: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ui_font = ui_font
        self.icon_font = icon_font
        self.payload: ModalPayload | None = None
        self._focus_target: QWidget | None = None
        self.setObjectName("premiumModalCard")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.MinimumExpanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)

        self.icon_badge = QLabel("")
        self.icon_badge.setObjectName("modalIconBadge")
        self.icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_badge.setFont(QFont(self.icon_font, 20))
        self.icon_badge.setFixedSize(42, 42)

        title_wrap = QVBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)
        title_wrap.setSpacing(2)
        self.title_label = QLabel("")
        self.title_label.setObjectName("modalTitle")
        self.title_label.setFont(QFont(self.ui_font, 14, QFont.Weight.DemiBold))
        self.subtitle_label = QLabel("")
        self.subtitle_label.setObjectName("modalSubtitle")
        self.subtitle_label.setFont(QFont(self.ui_font, 10))
        title_wrap.addWidget(self.title_label)
        title_wrap.addWidget(self.subtitle_label)

        self.close_button = QPushButton("×")
        self.close_button.setObjectName("modalCloseButton")
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setFixedSize(28, 28)
        self.close_button.clicked.connect(self.dismissed.emit)

        top.addWidget(self.icon_badge, 0, Qt.AlignmentFlag.AlignTop)
        top.addLayout(title_wrap, 1)
        top.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(top)

        self.body_label = QLabel("")
        self.body_label.setObjectName("modalBody")
        self.body_label.setWordWrap(True)
        self.body_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.body_label)

        self.actions_row = QHBoxLayout()
        self.actions_row.setContentsMargins(0, 4, 0, 0)
        self.actions_row.setSpacing(8)
        root.addLayout(self.actions_row)

    def set_payload(self, payload: ModalPayload) -> None:
        self.payload = payload
        self.title_label.setText(payload.title)
        self.subtitle_label.setText(payload.subtitle)
        self.subtitle_label.setVisible(bool(payload.subtitle.strip()))
        self.body_label.setText(payload.body)
        self.body_label.setVisible(bool(payload.body.strip()))
        if payload.icon_pixmap is not None and not payload.icon_pixmap.isNull():
            icon = payload.icon_pixmap.scaled(
                22,
                22,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.icon_badge.setPixmap(icon)
            self.icon_badge.setText("")
        else:
            self.icon_badge.setPixmap(QPixmap())
            self.icon_badge.setText(payload.icon_text)
        self._rebuild_actions(payload)
        self.adjustSize()

    def apply_theme(self, theme, icon_color: str, icon_bg: str) -> None:
        self.setStyleSheet(
            f"""
            QFrame#premiumModalCard {{
                background: {theme.panel_bg};
                border: 1px solid {theme.panel_border};
                border-radius: 26px;
            }}
            QLabel#modalTitle {{
                color: {theme.text};
            }}
            QLabel#modalSubtitle {{
                color: {theme.text_muted};
            }}
            QLabel#modalBody {{
                color: {theme.text};
                font-family: "{self.ui_font}";
                font-size: 11px;
                line-height: 1.4;
            }}
            QLabel#modalIconBadge {{
                color: {icon_color};
                background: {icon_bg};
                border-radius: 21px;
                font-family: "{self.icon_font}";
            }}
            QPushButton#modalCloseButton {{
                background: transparent;
                border: none;
                border-radius: 14px;
                color: {theme.text_muted};
                font-size: 16px;
            }}
            QPushButton#modalCloseButton:hover {{
                background: {theme.hover_bg};
                color: {theme.text};
            }}
            QPushButton#modalPrimaryButton {{
                background: {theme.primary};
                color: {theme.active_text};
                border: none;
                border-radius: 14px;
                padding: 10px 16px;
                font-weight: 700;
            }}
            QPushButton#modalPrimaryButton:hover {{
                background: {theme.primary_container};
            }}
            QPushButton#modalSecondaryButton {{
                background: {theme.surface_container_high};
                color: {theme.text};
                border: 1px solid {theme.panel_border};
                border-radius: 14px;
                padding: 10px 16px;
                font-weight: 600;
            }}
            QPushButton#modalSecondaryButton:hover {{
                background: {theme.hover_bg};
            }}
            """
        )

    def focus_primary_action(self) -> None:
        if self._focus_target is not None:
            self._focus_target.setFocus(Qt.FocusReason.PopupFocusReason)
            return
        self.close_button.setFocus(Qt.FocusReason.PopupFocusReason)

    def _rebuild_actions(self, payload: ModalPayload) -> None:
        self._focus_target = None
        while self.actions_row.count():
            item = self.actions_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        dismiss_button = QPushButton(payload.dismiss_label)
        dismiss_button.setObjectName("modalSecondaryButton")
        dismiss_button.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss_button.clicked.connect(self.dismissed.emit)
        self.actions_row.addWidget(dismiss_button)
        self._focus_target = dismiss_button
        for action in payload.actions:
            button = QPushButton(action.label)
            button.setObjectName("modalPrimaryButton" if action.primary else "modalSecondaryButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, key=action.key: self.actionTriggered.emit(key))
            self.actions_row.addWidget(button)
            if action.primary:
                self._focus_target = button
        self.actions_row.addStretch(1)


class PremiumModalPresenter(QWidget):
    actionTriggered = pyqtSignal(str, dict)
    dismissed = pyqtSignal(dict)

    def __init__(self, ui_font: str, icon_font: str, theme, motion: MotionSystem | None = None, parent: QWidget | None = None) -> None:
        super().__init__(None)
        self.motion = motion or MotionSystem(self)
        self.theme = theme
        self.ui_font = ui_font
        self.icon_font = icon_font
        self.motion_spec = ModalMotionSpec()
        self.layout_spec = ModalLayoutSpec()
        self.payload: ModalPayload | None = None
        self._animation: QParallelAnimationGroup | None = None
        self._phase = "hidden"
        self._host_parent = parent.window() if isinstance(parent, QWidget) else None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        if self._host_parent is not None:
            self._host_parent.installEventFilter(self)

        self.backdrop = BackdropLayer(self)
        self.backdrop.clicked.connect(self._dismiss)

        self.halo = HaloLayer(self)

        self.card_shell = QWidget(self)
        self.card_shell.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        shell_layout = QVBoxLayout(self.card_shell)
        shell_layout.setContentsMargins(self.layout_spec.shell_padding, self.layout_spec.shell_padding, self.layout_spec.shell_padding, self.layout_spec.shell_padding)
        shell_layout.setSpacing(0)

        self.card = ModalCard(ui_font, icon_font, self.card_shell)
        self.card.actionTriggered.connect(self._emit_action)
        self.card.dismissed.connect(self._dismiss)
        shell_layout.addWidget(self.card)

        self.card_transform = SurfaceTransformEffect(self.card_shell)
        self.card_shell.setGraphicsEffect(self.card_transform)

        self.card_shadow = QGraphicsDropShadowEffect(self.card)
        self.card_shadow.setBlurRadius(self.motion_spec.shadow_blur_soft)
        self.card_shadow.setOffset(QPointF(0.0, self.motion_spec.shadow_offset_soft))
        self.card_shadow.setColor(QColor(0, 0, 0, int(255 * self.motion_spec.shadow_alpha_soft)))
        self.card.setGraphicsEffect(self.card_shadow)
        self.shadow_proxy = ShadowProxy(self.card_shadow, QColor(0, 0, 0, int(255 * self.motion_spec.shadow_alpha_rest)), self)

        self._apply_theme()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if watched is self._host_parent and event.type() in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.Show):
            self._sync_geometry()
            self._layout_layers()
        return super().eventFilter(watched, event)

    def set_payload(self, payload: ModalPayload) -> None:
        self.payload = payload
        self.card.set_payload(payload)
        self._sync_geometry()
        self._layout_layers()

    def show_modal(self) -> None:
        if self.payload is None:
            return
        self._sync_geometry()
        self._layout_layers()
        self._cancel_animation()
        if self._phase == "hidden":
            self.backdrop.opacity = 0.0
            self.card_transform.opacity = 0.0
            self.card_transform.scale = self.motion_spec.enter_scale_start
            self.card_transform.xOffset = 0.0
            self.card_transform.yOffset = self.motion_spec.enter_offset_y
            self.halo.opacity = 0.0
            self.halo.blurRadius = self.motion_spec.halo_blur_start
            self.shadow_proxy.blur = self.motion_spec.shadow_blur_soft
            self.shadow_proxy.alpha = self.motion_spec.shadow_alpha_soft
            self.shadow_proxy.yOffset = self.motion_spec.shadow_offset_soft
        self.show()
        self.raise_()
        self.activateWindow()
        self.card.focus_primary_action()
        self._phase = "entering"
        self._animation = self.motion.parallel(
            "premium_modal:enter",
            [
                self._float_animation(self.backdrop, b"opacity", self.motion_spec.backdrop_opacity, self.motion_spec.duration_in, "enter"),
                self._float_animation(self.card_transform, b"opacity", 1.0, self.motion_spec.duration_in, "enter"),
                self._float_animation(self.card_transform, b"scale", 1.0, self.motion_spec.duration_in, "modal"),
                self._float_animation(self.card_transform, b"yOffset", 0.0, self.motion_spec.duration_in, "enter"),
                self._float_animation(self.halo, b"opacity", self.motion_spec.halo_opacity, self.motion_spec.duration_in, "enter"),
                self._float_animation(self.halo, b"blurRadius", self.motion_spec.halo_blur_end, self.motion_spec.duration_in, "settle"),
                self._float_animation(self.shadow_proxy, b"blur", self.motion_spec.shadow_blur_rest, self.motion_spec.duration_in, "settle"),
                self._float_animation(self.shadow_proxy, b"alpha", self.motion_spec.shadow_alpha_rest, self.motion_spec.duration_in, "settle"),
                self._float_animation(self.shadow_proxy, b"yOffset", self.motion_spec.shadow_offset_rest, self.motion_spec.duration_in, "settle"),
            ],
        )
        self._animation.finished.connect(self._mark_visible)

    def dismiss_modal(self) -> None:
        self._dismiss()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if self.payload is not None and self.payload.allow_escape and event.key() == Qt.Key.Key_Escape:
            self._dismiss()
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._layout_layers()

    def _sync_geometry(self) -> None:
        if self._host_parent is not None and self._host_parent.isVisible():
            self.setGeometry(self._host_parent.geometry())
            return
        app = QApplication.instance()
        screen = app.primaryScreen() if app is not None else None
        if screen is not None:
            self.setGeometry(screen.availableGeometry())

    def _layout_layers(self) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return
        self.backdrop.setGeometry(self.rect())
        available_width = max(280, self.width() - self.layout_spec.screen_margin * 2)
        card_width = min(self.layout_spec.max_width, max(self.layout_spec.min_width, available_width))
        self.card.setFixedWidth(card_width)
        self.card.adjustSize()
        shell_size = self.card.sizeHint()
        shell_width = shell_size.width() + self.layout_spec.shell_padding * 2
        shell_height = shell_size.height() + self.layout_spec.shell_padding * 2
        shell_width = min(shell_width, self.width() - self.layout_spec.screen_margin * 2)
        shell_height = min(shell_height, self.height() - self.layout_spec.screen_margin * 2)
        shell_x = (self.width() - shell_width) // 2
        shell_y = (self.height() - shell_height) // 2
        self.card_shell.setGeometry(shell_x, shell_y, shell_width, shell_height)
        self.halo.setGeometry(
            shell_x - self.layout_spec.halo_margin_x,
            shell_y - self.layout_spec.halo_margin_y,
            shell_width + self.layout_spec.halo_margin_x * 2,
            shell_height + self.layout_spec.halo_margin_y * 2,
        )
        self.halo.lower()
        self.backdrop.lower()
        self.card_shell.raise_()

    def _apply_theme(self) -> None:
        self.card.apply_theme(self.theme, self.theme.primary, self.theme.accent_soft)
        center = QColor(self.theme.media_active_start)
        center.setAlpha(150)
        edge = QColor(center)
        edge.setAlpha(0)
        self.halo.set_colors(center, edge)

    def _dismiss(self) -> None:
        if self.payload is None or self._phase == "hidden":
            self.hide()
            return
        self._cancel_animation()
        self._phase = "exiting"
        payload = self.payload
        self._animation = self.motion.parallel(
            "premium_modal:exit",
            [
                self._float_animation(self.backdrop, b"opacity", 0.0, self.motion_spec.duration_out, "exit"),
                self._float_animation(self.card_transform, b"opacity", 0.0, self.motion_spec.duration_out, "exit"),
                self._float_animation(self.card_transform, b"scale", self.motion_spec.exit_scale_end, self.motion_spec.duration_out, "exit"),
                self._float_animation(self.card_transform, b"yOffset", self.motion_spec.exit_offset_y, self.motion_spec.duration_out, "exit"),
                self._float_animation(self.halo, b"opacity", 0.0, self.motion_spec.duration_out, "exit"),
                self._float_animation(self.halo, b"blurRadius", self.motion_spec.halo_blur_start, self.motion_spec.duration_out, "exit"),
                self._float_animation(self.shadow_proxy, b"blur", self.motion_spec.shadow_blur_soft, self.motion_spec.duration_out, "exit"),
                self._float_animation(self.shadow_proxy, b"alpha", self.motion_spec.shadow_alpha_soft, self.motion_spec.duration_out, "exit"),
                self._float_animation(self.shadow_proxy, b"yOffset", self.motion_spec.shadow_offset_soft, self.motion_spec.duration_out, "exit"),
            ],
        )
        self._animation.finished.connect(lambda payload=payload: self._finish_dismiss(payload))

    def _finish_dismiss(self, payload: ModalPayload | None) -> None:
        self.hide()
        self.payload = None
        self._phase = "hidden"
        if payload is not None:
            self.dismissed.emit(dict(payload.metadata))

    def _emit_action(self, key: str) -> None:
        if self.payload is not None:
            self.actionTriggered.emit(key, dict(self.payload.metadata))
        self._dismiss()

    def _mark_visible(self) -> None:
        if self._phase != "exiting":
            self._phase = "visible"

    def _cancel_animation(self) -> None:
        if self._animation is not None:
            self._animation.stop()
            self._animation = None
        self.motion.cancel("premium_modal:enter")
        self.motion.cancel("premium_modal:exit")

    def _float_animation(
        self,
        target: QObject,
        prop: bytes,
        end_value: float,
        duration: int,
        easing: str,
    ) -> QPropertyAnimation:
        animation = QPropertyAnimation(target, prop, self)
        prop_name = prop.decode("utf-8")
        current_value = target.property(prop_name)
        try:
            start_value = float(current_value)
        except (TypeError, ValueError):
            start_value = end_value
        animation.setStartValue(start_value)
        animation.setEndValue(end_value)
        animation.setDuration(max(1, int(duration)))
        animation.setEasingCurve(self.motion.easing(easing))
        return animation


class PremiumModalHost(QObject):
    actionTriggered = pyqtSignal(str, dict)
    dismissed = pyqtSignal(dict)

    def __init__(
        self,
        ui_font: str,
        icon_font: str,
        theme,
        *,
        motion: MotionSystem | None = None,
        parent: QWidget | None = None,
        stack_policy: str = ModalStackPolicy.REPLACE,
    ) -> None:
        super().__init__(parent)
        self.motion = motion or MotionSystem(self)
        self.theme = theme
        self.ui_font = ui_font
        self.icon_font = icon_font
        self.stack_policy = stack_policy
        self._queue: list[ModalPayload] = []
        self.presenter = PremiumModalPresenter(ui_font, icon_font, theme, self.motion, parent)
        self.presenter.actionTriggered.connect(self.actionTriggered)
        self.presenter.dismissed.connect(self._handle_dismissed)

    def show_payload(self, payload: ModalPayload) -> None:
        if self.presenter.isVisible() and self.presenter.payload is not None:
            if self.stack_policy == ModalStackPolicy.QUEUE:
                self._queue.append(payload)
                return
            if self.stack_policy == ModalStackPolicy.STACK:
                self._queue.insert(0, payload)
                self.presenter.dismiss_modal()
                return
            self._queue.clear()
        self.presenter.set_payload(payload)
        self.presenter.show_modal()

    def dismiss_current(self) -> None:
        self.presenter.dismiss_modal()

    def set_stack_policy(self, policy: str) -> None:
        self.stack_policy = policy

    def update_theme(self, theme) -> None:
        self.theme = theme
        self.presenter.theme = theme
        self.presenter._apply_theme()

    def _handle_dismissed(self, metadata: dict) -> None:
        self.dismissed.emit(metadata)
        if not self._queue:
            return
        next_payload = self._queue.pop(0)
        self.presenter.set_payload(next_payload)
        self.presenter.show_modal()
