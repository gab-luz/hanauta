#include <QtCore/QCommandLineOption>
#include <QtCore/QCommandLineParser>
#include <QtCore/QDir>
#include <QtCore/QFileInfo>
#include <QtCore/QUrl>
#include <QtGui/QGuiApplication>
#include <QtGui/QImage>
#include <QtQuick/QQuickView>

static QString mustBeAbsoluteFile(const QString &path)
{
    QFileInfo info(path);
    if (info.isAbsolute())
        return info.absoluteFilePath();
    return QDir::current().absoluteFilePath(path);
}

int main(int argc, char **argv)
{
    qputenv("QT_ENABLE_HIGHDPI_SCALING", "1");
    if (qEnvironmentVariableIsEmpty("QT_QUICK_BACKEND"))
        qputenv("QT_QUICK_BACKEND", "software");

    QGuiApplication app(argc, argv);
    QCommandLineParser parser;
    parser.setApplicationDescription("Render Hanauta QML lockscreen to a PNG.");
    parser.addHelpOption();

    QCommandLineOption qmlOpt(QStringList() << "qml", "Path to Lockscreen.qml", "qml");
    QCommandLineOption widthOpt(QStringList() << "width", "Width in pixels", "width", "1920");
    QCommandLineOption heightOpt(QStringList() << "height", "Height in pixels", "height", "1080");
    QCommandLineOption outOpt(QStringList() << "out", "Output PNG path", "out");

    parser.addOption(qmlOpt);
    parser.addOption(widthOpt);
    parser.addOption(heightOpt);
    parser.addOption(outOpt);
    parser.process(app);

    const QString outPath = parser.value(outOpt);
    if (outPath.isEmpty()) {
        fprintf(stderr, "Missing required --out\n");
        return 2;
    }

    QString qmlPath = parser.value(qmlOpt);
    if (qmlPath.isEmpty()) {
        // Default to sibling Lockscreen.qml next to the binary's working dir hint:
        qmlPath = "Lockscreen.qml";
    }
    qmlPath = mustBeAbsoluteFile(qmlPath);

    bool okW = false;
    bool okH = false;
    const int width = parser.value(widthOpt).toInt(&okW);
    const int height = parser.value(heightOpt).toInt(&okH);
    if (!okW || !okH || width <= 0 || height <= 0) {
        fprintf(stderr, "Invalid --width/--height\n");
        return 2;
    }

    QQuickView view;
    view.setResizeMode(QQuickView::SizeRootObjectToView);
    view.setSource(QUrl::fromLocalFile(qmlPath));
    view.resize(width, height);
    view.show();
    app.processEvents();

    const QImage img = view.grabWindow();
    if (img.isNull()) {
        fprintf(stderr, "Failed to grab window\n");
        return 3;
    }

    QFileInfo outInfo(outPath);
    QDir().mkpath(outInfo.absolutePath());
    if (!img.save(outInfo.absoluteFilePath(), "PNG")) {
        fprintf(stderr, "Failed to save PNG\n");
        return 3;
    }

    return 0;
}

