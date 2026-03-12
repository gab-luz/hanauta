#include "XSecurelockWindow.hpp"

#include <QGuiApplication>
#include <QScreen>
#include <QWindow>

#include <X11/Xlib.h>

XSecurelockWindow::XSecurelockWindow(QQuickView *view) : m_view(view) {}
XSecurelockWindow::XSecurelockWindow(QWidget *widget) : m_widget(widget) {}

void XSecurelockWindow::attachAndShow() {
    if (qEnvironmentVariableIsSet("XSCREENSAVER_WINDOW")) {
        attachToScreensaverWindow();
        return;
    }
    showStandalone();
}

void XSecurelockWindow::attachToScreensaverWindow() {
    bool ok = false;
    const WId parentId = QString::fromLocal8Bit(qgetenv("XSCREENSAVER_WINDOW")).toULongLong(&ok, 0);
    if (!ok || parentId == 0) {
        showStandalone();
        return;
    }

    Display *display = XOpenDisplay(nullptr);
    if (display == nullptr) {
        showStandalone();
        return;
    }

    XWindowAttributes attrs {};
    if (XGetWindowAttributes(display, static_cast<Window>(parentId), &attrs) == 0) {
        XCloseDisplay(display);
        showStandalone();
        return;
    }

    if (m_view != nullptr) {
        m_view->setFlags(Qt::FramelessWindowHint | Qt::BypassWindowManagerHint | Qt::X11BypassWindowManagerHint);
        m_view->setColor(Qt::transparent);
        m_view->setGeometry(0, 0, attrs.width, attrs.height);
        m_view->show();
        m_view->raise();
    } else if (m_widget != nullptr) {
        m_widget->setWindowFlags(Qt::FramelessWindowHint | Qt::BypassWindowManagerHint | Qt::X11BypassWindowManagerHint);
        m_widget->setGeometry(0, 0, attrs.width, attrs.height);
        m_widget->show();
        m_widget->raise();
        m_widget->activateWindow();
        m_widget->setFocus();
    }

    const WId childId = m_view != nullptr ? m_view->winId() : m_widget->winId();
    XReparentWindow(display, static_cast<Window>(childId), static_cast<Window>(parentId), 0, 0);
    XMoveResizeWindow(display, static_cast<Window>(childId), 0, 0, attrs.width, attrs.height);
    XMapRaised(display, static_cast<Window>(childId));
    XSync(display, False);
    XCloseDisplay(display);
}

void XSecurelockWindow::showStandalone() {
    QScreen *screen = QGuiApplication::primaryScreen();
    const QRect geometry = screen != nullptr ? screen->virtualGeometry() : QRect();

    if (m_view != nullptr) {
        m_view->setFlags(
            Qt::FramelessWindowHint
            | Qt::WindowStaysOnTopHint
            | Qt::Tool
            | Qt::BypassWindowManagerHint
            | Qt::X11BypassWindowManagerHint
        );
        m_view->setColor(Qt::transparent);
        if (!geometry.isNull()) {
            m_view->setGeometry(geometry);
        }
        m_view->showFullScreen();
        m_view->raise();
        m_view->requestActivate();
        return;
    }

    if (m_widget != nullptr) {
        m_widget->setWindowFlags(
            Qt::FramelessWindowHint
            | Qt::WindowStaysOnTopHint
            | Qt::Tool
            | Qt::BypassWindowManagerHint
            | Qt::X11BypassWindowManagerHint
        );
        if (!geometry.isNull()) {
            m_widget->setGeometry(geometry);
        }
        m_widget->showFullScreen();
        m_widget->raise();
        m_widget->activateWindow();
        m_widget->setFocus();
    }
}
