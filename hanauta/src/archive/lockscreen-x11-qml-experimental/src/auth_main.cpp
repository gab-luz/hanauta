#include "AuthBridge.hpp"
#include "AuthWindow.hpp"
#include "XSecurelockWindow.hpp"

#include <QApplication>

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("auth_hanauta"));
    app.setQuitOnLastWindowClosed(false);

    AuthBridge bridge;
    AuthWindow view(&bridge);

    QObject::connect(&bridge, &AuthBridge::requestQuit, &app, [&](int exitCode) {
        app.exit(exitCode);
    });

    XSecurelockWindow window(&view);
    window.attachAndShow();
    return app.exec();
}
