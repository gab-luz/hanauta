#include <QApplication>
#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFont>
#include <QFontDatabase>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPainter>
#include <QPainterPath>
#include <QPolygonF>
#include <QProcess>
#include <QResizeEvent>
#include <QRegion>
#include <QScreen>
#include <QSet>
#include <QShowEvent>
#include <QTimer>
#include <QWidget>
#include <algorithm>
#include <cmath>
#include <functional>

namespace {

constexpr int kDefaultBarHeight = 45;

struct ThemePalette {
    bool useMatugen = false;
    QString primary = "#D0BCFF";
    QString onPrimary = "#381E72";
    QString primaryContainer = "#4F378B";
    QString onPrimaryContainer = "#EADDFF";
    QString secondary = "#CCC2DC";
    QString surfaceContainer = "#211F26";
    QString surfaceContainerHigh = "#2B2930";
    QString onSurface = "#E6E0E9";
    QString onSurfaceVariant = "#CAC4D0";
    QString outline = "#938F99";
    QString error = "#F2B8B5";
};

QString settingsFilePath() {
    return QDir::homePath() + "/.local/state/hanauta/notification-center/settings.json";
}

QString paletteFilePath() {
    return QDir::homePath() + "/.local/state/hanauta/theme/pyqt_palette.json";
}

QString normalizeHex(const QString &value, const QString &fallback) {
    QString color = value.trimmed();
    if (!color.startsWith('#')) {
        color.prepend('#');
    }
    if (color.size() != 7) {
        return fallback;
    }
    bool ok = false;
    color.mid(1).toInt(&ok, 16);
    return ok ? color.toUpper() : fallback;
}

QColor withAlpha(const QString &hex, qreal alpha) {
    QColor color(normalizeHex(hex, "#000000"));
    color.setAlphaF(std::clamp(alpha, 0.0, 1.0));
    return color;
}

ThemePalette loadThemePalette() {
    ThemePalette palette;
    QFile file(paletteFilePath());
    if (!file.open(QIODevice::ReadOnly)) {
        return palette;
    }
    const QJsonDocument doc = QJsonDocument::fromJson(file.readAll());
    const QJsonObject obj = doc.object();
    if (!obj.value("use_matugen").toBool(false)) {
        return palette;
    }
    palette.useMatugen = true;
    palette.primary = normalizeHex(obj.value("primary").toString(palette.primary), palette.primary);
    palette.onPrimary = normalizeHex(obj.value("on_primary").toString(palette.onPrimary), palette.onPrimary);
    palette.primaryContainer = normalizeHex(obj.value("primary_container").toString(palette.primaryContainer), palette.primaryContainer);
    palette.onPrimaryContainer = normalizeHex(obj.value("on_primary_container").toString(palette.onPrimaryContainer), palette.onPrimaryContainer);
    palette.secondary = normalizeHex(obj.value("secondary").toString(palette.secondary), palette.secondary);
    palette.surfaceContainer = normalizeHex(obj.value("surface_container").toString(palette.surfaceContainer), palette.surfaceContainer);
    palette.surfaceContainerHigh = normalizeHex(obj.value("surface_container_high").toString(palette.surfaceContainerHigh), palette.surfaceContainerHigh);
    palette.onSurface = normalizeHex(obj.value("on_surface").toString(palette.onSurface), palette.onSurface);
    palette.onSurfaceVariant = normalizeHex(obj.value("on_surface_variant").toString(palette.onSurfaceVariant), palette.onSurfaceVariant);
    palette.outline = normalizeHex(obj.value("outline").toString(palette.outline), palette.outline);
    palette.error = normalizeHex(obj.value("error").toString(palette.error), palette.error);
    return palette;
}

QJsonObject loadSettingsObject() {
    QFile file(settingsFilePath());
    if (!file.open(QIODevice::ReadOnly)) {
        return {};
    }
    const QJsonDocument doc = QJsonDocument::fromJson(file.readAll());
    return doc.object();
}

QString runCommand(const QStringList &command, int timeoutMs = 2000) {
    if (command.isEmpty()) {
        return {};
    }
    QProcess process;
    process.start(command.first(), command.mid(1));
    if (!process.waitForFinished(timeoutMs)) {
        process.kill();
        process.waitForFinished(250);
        return {};
    }
    return QString::fromUtf8(process.readAllStandardOutput()).trimmed();
}

QString focusedWorkspaceName() {
    const QString raw = runCommand({"i3-msg", "-t", "get_workspaces"});
    const QJsonDocument doc = QJsonDocument::fromJson(raw.toUtf8());
    if (!doc.isArray()) {
        return {};
    }
    for (const QJsonValue &value : doc.array()) {
        const QJsonObject obj = value.toObject();
        if (obj.value("focused").toBool(false)) {
            return obj.value("name").toString().trimmed();
        }
    }
    return {};
}

QJsonObject focusedWorkspaceRect() {
    const QString raw = runCommand({"i3-msg", "-t", "get_workspaces"});
    const QJsonDocument doc = QJsonDocument::fromJson(raw.toUtf8());
    if (!doc.isArray()) {
        return {};
    }
    for (const QJsonValue &value : doc.array()) {
        const QJsonObject obj = value.toObject();
        if (obj.value("focused").toBool(false)) {
            return obj.value("rect").toObject();
        }
    }
    return {};
}

void collectLeafWindows(const QJsonObject &node, QList<QJsonObject> &windows) {
    for (const char *key : {"nodes", "floating_nodes"}) {
        const QJsonArray children = node.value(QLatin1String(key)).toArray();
        for (const QJsonValue &child : children) {
            collectLeafWindows(child.toObject(), windows);
        }
    }
    if (!node.value("window").isNull()) {
        windows.append(node);
    }
}

bool focusedWorkspaceHasRealWindows() {
    const QString workspace = focusedWorkspaceName();
    if (workspace.isEmpty()) {
        return false;
    }
    const QJsonDocument treeDoc = QJsonDocument::fromJson(runCommand({"i3-msg", "-t", "get_tree"}, 3000).toUtf8());
    if (!treeDoc.isObject()) {
        return false;
    }

    std::function<QJsonObject(const QJsonObject &)> findWorkspace = [&](const QJsonObject &node) -> QJsonObject {
        if (node.value("type").toString() == "workspace" && node.value("name").toString().trimmed() == workspace) {
            return node;
        }
        for (const char *key : {"nodes", "floating_nodes"}) {
            const QJsonArray children = node.value(QLatin1String(key)).toArray();
            for (const QJsonValue &child : children) {
                const QJsonObject found = findWorkspace(child.toObject());
                if (!found.isEmpty()) {
                    return found;
                }
            }
        }
        return {};
    };

    const QJsonObject workspaceNode = findWorkspace(treeDoc.object());
    if (workspaceNode.isEmpty()) {
        return false;
    }

    QList<QJsonObject> windows;
    collectLeafWindows(workspaceNode, windows);
    const QSet<QString> ignoredClasses = {
        "CyberBar",
        "CyberDock",
        "HanautaDesktopClock",
        "HanautaClock",
        "HanautaHotkeys",
    };
    const QSet<QString> ignoredTitles = {
        "CyberBar",
        "Hanauta Desktop Clock",
        "Hanauta Clock",
    };

    for (const QJsonObject &window : windows) {
        const QJsonObject props = window.value("window_properties").toObject();
        const QString wmClass = props.value("class").toString().trimmed();
        const QString title = window.value("name").toString().trimmed();
        if (ignoredClasses.contains(wmClass) || ignoredTitles.contains(title)) {
            continue;
        }
        return true;
    }
    return false;
}

int loadBarHeight() {
    const QJsonObject bar = loadSettingsObject().value("bar").toObject();
    return std::clamp(bar.value("bar_height").toInt(kDefaultBarHeight), 32, 72);
}

}  // namespace

class HanautaClockWidget final : public QWidget {
public:
    HanautaClockWidget() {
        loadFonts();
        refreshSettings();
        setAttribute(Qt::WA_TranslucentBackground, true);
        setAttribute(Qt::WA_ShowWithoutActivating, true);
        setWindowFlags(Qt::FramelessWindowHint | Qt::Tool | Qt::WindowStaysOnBottomHint);
        setWindowTitle("Hanauta Clock");
        applySize();
        placeWindow();
        updateMask();

        auto *tickTimer = new QTimer(this);
        connect(tickTimer, &QTimer::timeout, this, qOverload<>(&HanautaClockWidget::update));
        tickTimer->start(1000);

        auto *stateTimer = new QTimer(this);
        connect(stateTimer, &QTimer::timeout, this, &HanautaClockWidget::syncState);
        stateTimer->start(1200);
    }

protected:
    void showEvent(QShowEvent *event) override {
        QWidget::showEvent(event);
        setWindowClass();
        QTimer::singleShot(150, this, &HanautaClockWidget::applyI3Rules);
        QTimer::singleShot(200, this, &HanautaClockWidget::syncState);
    }

    void resizeEvent(QResizeEvent *event) override {
        QWidget::resizeEvent(event);
        updateMask();
    }

    void paintEvent(QPaintEvent *event) override {
        Q_UNUSED(event);
        QPainter painter(this);
        painter.setRenderHint(QPainter::Antialiasing, true);

        const QRectF rect = this->rect().adjusted(10, 10, -10, -10);
        const QPointF center = rect.center();
        const qreal outerRadius = std::min(rect.width(), rect.height()) / 2.0 - 6.0;
        const qreal innerRadius = outerRadius * 0.90;

        QPainterPath face;
        constexpr int scallops = 18;
        for (int index = 0; index <= scallops * 6; ++index) {
            const qreal angle = (M_PI * 2.0 * index) / static_cast<qreal>(scallops * 6);
            const qreal pulse = std::sin(angle * scallops);
            const qreal radius = outerRadius + pulse * (outerRadius * 0.045);
            const QPointF point(
                center.x() + std::cos(angle - M_PI / 2.0) * radius,
                center.y() + std::sin(angle - M_PI / 2.0) * radius);
            if (index == 0) {
                face.moveTo(point);
            } else {
                face.lineTo(point);
            }
        }
        face.closeSubpath();

        painter.fillPath(face, faceFill_);

        QPen tickPen(tickColor_);
        tickPen.setWidthF(std::max(2.0, outerRadius * 0.012));
        tickPen.setCapStyle(Qt::RoundCap);
        painter.setPen(tickPen);
        for (int index = 0; index < 60; ++index) {
            const qreal angle = (M_PI * 2.0 * index) / 60.0 - M_PI / 2.0;
            const bool major = index % 5 == 0;
            const qreal tickLength = innerRadius * (major ? 0.105 : 0.055);
            const qreal outer = innerRadius * 0.92;
            const qreal inner = outer - tickLength;
            painter.drawLine(
                QPointF(center.x() + std::cos(angle) * inner, center.y() + std::sin(angle) * inner),
                QPointF(center.x() + std::cos(angle) * outer, center.y() + std::sin(angle) * outer));
        }

        const QDateTime now = QDateTime::currentDateTime();
        QString hour = now.toString(use24Hour_ ? "HH" : "hh");
        const QString minute = now.toString("mm");

        painter.setPen(digitalColor_);
        painter.setFont(QFont(displayFont_, std::max(44, static_cast<int>(outerRadius * 0.46)), QFont::Bold));
        painter.drawText(rect.adjusted(0, static_cast<int>(-outerRadius * 0.18), 0, 0), Qt::AlignCenter, hour);
        painter.drawText(rect.adjusted(0, static_cast<int>(outerRadius * 0.24), 0, 0), Qt::AlignCenter, minute);

        const qreal hourAngle = (((now.time().hour() % 12) + now.time().minute() / 60.0) * (M_PI * 2.0 / 12.0)) - M_PI / 2.0;
        const qreal minuteAngle = ((now.time().minute() + now.time().second() / 60.0) * (M_PI * 2.0 / 60.0)) - M_PI / 2.0;
        const qreal secondAngle = (now.time().second() * (M_PI * 2.0 / 60.0)) - M_PI / 2.0;

        painter.setPen(QPen(hourHandColor_, std::max(10.0, outerRadius * 0.072), Qt::SolidLine, Qt::RoundCap));
        painter.drawLine(center, QPointF(center.x() + std::cos(hourAngle) * innerRadius * 0.42, center.y() + std::sin(hourAngle) * innerRadius * 0.42));

        painter.setPen(QPen(minuteHandColor_, std::max(8.0, outerRadius * 0.052), Qt::SolidLine, Qt::RoundCap));
        painter.drawLine(center, QPointF(center.x() + std::cos(minuteAngle) * innerRadius * 0.62, center.y() + std::sin(minuteAngle) * innerRadius * 0.62));

        if (showSeconds_) {
            painter.setPen(QPen(secondHandColor_, std::max(3.0, outerRadius * 0.018), Qt::SolidLine, Qt::RoundCap));
            painter.drawLine(center, QPointF(center.x() + std::cos(secondAngle) * innerRadius * 0.70, center.y() + std::sin(secondAngle) * innerRadius * 0.70));
        }

        painter.setPen(Qt::NoPen);
        painter.setBrush(centerOuterColor_);
        painter.drawEllipse(center, std::max(8.0, outerRadius * 0.05), std::max(8.0, outerRadius * 0.05));
        painter.setBrush(centerInnerColor_);
        painter.drawEllipse(center, std::max(3.0, outerRadius * 0.018), std::max(3.0, outerRadius * 0.018));
    }

private:
    void loadFonts() {
        const QString fontRoot = QCoreApplication::applicationDirPath() + "/../assets/fonts/";
        QFontDatabase::addApplicationFont(fontRoot + "InterVariable.ttf");
        QFontDatabase::addApplicationFont(fontRoot + "Outfit-VariableFont_wght.ttf");
        displayFont_ = QFont("Outfit").exactMatch() ? "Outfit" : "Sans Serif";
    }

    void refreshSettings() {
        const QJsonObject settings = loadSettingsObject();
        const QJsonObject clock = settings.value("clock").toObject();
        const QJsonObject region = settings.value("region").toObject();
        const QJsonObject services = settings.value("services").toObject();
        const QJsonObject service = services.value("desktop_clock_widget").toObject();

        clockSize_ = std::clamp(clock.value("size").toInt(320), 220, 520);
        showSeconds_ = clock.value("show_seconds").toBool(true);
        use24Hour_ = region.value("use_24_hour").toBool(false);
        positionX_ = clock.value("position_x").toInt(-1);
        positionY_ = clock.value("position_y").toInt(-1);
        enabled_ = service.isEmpty() ? true : service.value("enabled").toBool(true);
        applyTheme(loadThemePalette());
    }

    void applyTheme(const ThemePalette &palette) {
        if (palette.useMatugen) {
            faceFill_ = withAlpha(palette.secondary, 0.92);
            tickColor_ = withAlpha(palette.onSurface, 0.42);
            digitalColor_ = withAlpha(palette.onSurface, 0.28);
            hourHandColor_ = withAlpha(palette.onSurface, 0.70);
            minuteHandColor_ = withAlpha(palette.primary, 0.96);
            secondHandColor_ = withAlpha(palette.error, 0.82);
            centerOuterColor_ = withAlpha(palette.primary, 0.95);
            centerInnerColor_ = withAlpha(palette.primaryContainer, 0.96);
            return;
        }
        faceFill_ = QColor("#415050");
        faceFill_.setAlphaF(0.96);
        tickColor_ = QColor("#EEF6F4");
        tickColor_.setAlphaF(0.62);
        digitalColor_ = QColor("#D6DFDC");
        digitalColor_.setAlphaF(0.32);
        hourHandColor_ = QColor("#C8D0CF");
        hourHandColor_.setAlphaF(0.78);
        minuteHandColor_ = QColor("#DFF7F2");
        minuteHandColor_.setAlphaF(0.98);
        secondHandColor_ = QColor("#E8A4A0");
        secondHandColor_.setAlphaF(0.94);
        centerOuterColor_ = QColor("#BFE5E0");
        centerOuterColor_.setAlphaF(0.98);
        centerInnerColor_ = QColor("#F3FCFA");
        centerInnerColor_.setAlphaF(0.98);
    }

    void applySize() {
        setFixedSize(clockSize_, clockSize_);
    }

    void placeWindow() {
        if (positionX_ >= 0 && positionY_ >= 0) {
            move(positionX_, positionY_);
            return;
        }
        const QJsonObject rect = focusedWorkspaceRect();
        if (!rect.isEmpty()) {
            const int x = rect.value("x").toInt(0);
            const int y = rect.value("y").toInt(0);
            const int width = rect.value("width").toInt(this->width());
            move(x + (width - this->width()) / 2, y + loadBarHeight() + 24);
            return;
        }
        if (QScreen *screen = QGuiApplication::primaryScreen()) {
            const QRect available = screen->availableGeometry();
            move(available.x() + (available.width() - width()) / 2, available.y() + loadBarHeight() + 24);
        }
    }

    void updateMask() {
        QPainterPath face;
        const QRectF rect = this->rect().adjusted(10, 10, -10, -10);
        const QPointF center = rect.center();
        const qreal outerRadius = std::min(rect.width(), rect.height()) / 2.0 - 6.0;
        constexpr int scallops = 18;
        for (int index = 0; index <= scallops * 6; ++index) {
            const qreal angle = (M_PI * 2.0 * index) / static_cast<qreal>(scallops * 6);
            const qreal pulse = std::sin(angle * scallops);
            const qreal radius = outerRadius + pulse * (outerRadius * 0.045);
            const QPointF point(
                center.x() + std::cos(angle - M_PI / 2.0) * radius,
                center.y() + std::sin(angle - M_PI / 2.0) * radius);
            if (index == 0) {
                face.moveTo(point);
            } else {
                face.lineTo(point);
            }
        }
        face.closeSubpath();
        setMask(QRegion(face.toFillPolygon().toPolygon()));
    }

    void setWindowClass() {
        const QString wid = QStringLiteral("0x%1").arg(winId(), 0, 16);
        QProcess::execute("xprop", {"-id", wid, "-f", "_NET_WM_NAME", "8t", "-set", "_NET_WM_NAME", "Hanauta Clock"});
        QProcess::execute("xprop", {"-id", wid, "-f", "WM_CLASS", "8s", "-set", "WM_CLASS", "HanautaClock"});
    }

    void applyI3Rules() {
        QProcess::execute("i3-msg", {R"([title="Hanauta Clock"])", "floating enable, border pixel 0"});
    }

    void syncState() {
        refreshSettings();
        if (!enabled_ || focusedWorkspaceHasRealWindows()) {
            close();
            qApp->quit();
            return;
        }
        placeWindow();
        if (!isVisible()) {
            show();
        }
        update();
    }

    QString displayFont_ = "Sans Serif";
    int clockSize_ = 320;
    int positionX_ = -1;
    int positionY_ = -1;
    bool showSeconds_ = true;
    bool use24Hour_ = false;
    bool enabled_ = true;
    QColor faceFill_;
    QColor tickColor_;
    QColor digitalColor_;
    QColor hourHandColor_;
    QColor minuteHandColor_;
    QColor secondHandColor_;
    QColor centerOuterColor_;
    QColor centerInnerColor_;
};

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    HanautaClockWidget widget;
    widget.show();
    return app.exec();
}
