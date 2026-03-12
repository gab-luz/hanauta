#include "XSecurelockWindow.hpp"

#include <QGuiApplication>
#include <QLibraryInfo>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQuickView>
#include <QDateTime>
#include <QFileInfo>
#include <QTimer>

class SaverBridge : public QObject {
    Q_OBJECT
    Q_PROPERTY(QString currentTime READ currentTime NOTIFY changed)
    Q_PROPERTY(QString currentDate READ currentDate NOTIFY changed)
    Q_PROPERTY(QString wallpaperSource READ wallpaperSource CONSTANT)

public:
    explicit SaverBridge(QObject *parent = nullptr) : QObject(parent) {
        QString wallpaper = QString::fromLocal8Bit(qgetenv("HOME")) + QStringLiteral("/.wallpapers/wallpaper.png");
        if (QFileInfo::exists(wallpaper)) {
            m_wallpaperSource = QStringLiteral("file://") + wallpaper;
        }

        connect(&m_timer, &QTimer::timeout, this, &SaverBridge::tick);
        m_timer.start(1000);
        tick();
    }

    QString currentTime() const { return m_currentTime; }
    QString currentDate() const { return m_currentDate; }
    QString wallpaperSource() const { return m_wallpaperSource; }

signals:
    void changed();

private:
    void tick() {
        const QDateTime now = QDateTime::currentDateTime();
        m_currentTime = now.toString(QStringLiteral("HH:mm"));
        m_currentDate = now.toString(QStringLiteral("dddd • dd MMMM yyyy"));
        emit changed();
    }

    QString m_currentTime;
    QString m_currentDate;
    QString m_wallpaperSource;
    QTimer m_timer;
};

int main(int argc, char *argv[]) {
    QGuiApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("saver_hanauta"));
    app.setQuitOnLastWindowClosed(false);

    SaverBridge bridge;
    QQuickView view;
    view.engine()->addImportPath(QLibraryInfo::path(QLibraryInfo::LibraryPath::QmlImportsPath));
    view.engine()->addPluginPath(QLibraryInfo::path(QLibraryInfo::LibraryPath::PluginsPath));
    view.rootContext()->setContextProperty(QStringLiteral("authBridge"), &bridge);
    view.setResizeMode(QQuickView::SizeRootObjectToView);
    view.setSource(QUrl(QStringLiteral("qrc:/qml/MainSaver.qml")));

    XSecurelockWindow window(&view);
    window.attachAndShow();
    return app.exec();
}

#include "saver_main.moc"
