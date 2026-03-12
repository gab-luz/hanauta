#pragma once

#include <QWidget>
#include <QQuickView>

class XSecurelockWindow {
public:
    explicit XSecurelockWindow(QQuickView *view);
    explicit XSecurelockWindow(QWidget *widget);
    void attachAndShow();

private:
    void attachToScreensaverWindow();
    void showStandalone();

    QQuickView *m_view = nullptr;
    QWidget *m_widget = nullptr;
};
