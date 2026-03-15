#include <QCoreApplication>
#include <QCursor>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QFontDatabase>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMap>
#include <QProcess>
#include <QQuickStyle>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QScreen>
#include <QSet>
#include <QStandardPaths>
#include <QStringList>
#include <QTimer>
#include <QUrl>

#include <algorithm>
#include <cstdio>

namespace {

QString repoRoot() {
    return QDir(QCoreApplication::applicationDirPath() + "/..").absolutePath();
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

QString rgba(const QString &hex, qreal alpha) {
    const QString color = normalizeHex(hex, "#000000");
    const int r = color.mid(1, 2).toInt(nullptr, 16);
    const int g = color.mid(3, 2).toInt(nullptr, 16);
    const int b = color.mid(5, 2).toInt(nullptr, 16);
    const int a = qBound(0, static_cast<int>(alpha * 255.0), 255);
    return QStringLiteral("#%1%2%3%4")
        .arg(a, 2, 16, QLatin1Char('0'))
        .arg(r, 2, 16, QLatin1Char('0'))
        .arg(g, 2, 16, QLatin1Char('0'))
        .arg(b, 2, 16, QLatin1Char('0'))
        .toUpper();
}

QString blend(const QString &left, const QString &right, qreal ratio) {
    const QString a = normalizeHex(left, "#000000");
    const QString b = normalizeHex(right, "#000000");
    const qreal t = qBound<qreal>(0.0, ratio, 1.0);
    const int ar = a.mid(1, 2).toInt(nullptr, 16);
    const int ag = a.mid(3, 2).toInt(nullptr, 16);
    const int ab = a.mid(5, 2).toInt(nullptr, 16);
    const int br = b.mid(1, 2).toInt(nullptr, 16);
    const int bg = b.mid(3, 2).toInt(nullptr, 16);
    const int bb = b.mid(5, 2).toInt(nullptr, 16);
    return QStringLiteral("#%1%2%3")
        .arg(static_cast<int>(ar + ((br - ar) * t)), 2, 16, QLatin1Char('0'))
        .arg(static_cast<int>(ag + ((bg - ag) * t)), 2, 16, QLatin1Char('0'))
        .arg(static_cast<int>(ab + ((bb - ab) * t)), 2, 16, QLatin1Char('0'))
        .toUpper();
}

QString runCommandText(const QStringList &command, int timeoutMs = 8000) {
    if (command.isEmpty()) {
        return {};
    }
    QProcess process;
    process.start(command.first(), command.mid(1));
    if (!process.waitForFinished(timeoutMs)) {
        process.kill();
        return {};
    }
    return QString::fromUtf8(process.readAllStandardOutput()).trimmed();
}

void loadFonts() {
    const QString root = repoRoot();
    const QStringList fonts = {
        root + "/assets/fonts/InterVariable.ttf",
        root + "/assets/fonts/MaterialIcons-Regular.ttf",
    };
    for (const QString &path : fonts) {
        if (QFile::exists(path)) {
            QFontDatabase::addApplicationFont(path);
        }
    }
}

QString materialGlyph(const QString &name) {
    static const QMap<QString, QString> icons = {
        {"check_circle", QString::fromUtf8("\uE86C")},
        {"close", QString::fromUtf8("\uE5CD")},
        {"lock", QString::fromUtf8("\uE897")},
        {"lock_open", QString::fromUtf8("\uE898")},
        {"refresh", QString::fromUtf8("\uE5D5")},
        {"signal_wifi_0_bar", QString::fromUtf8("\uE1DA")},
        {"signal_wifi_1_bar", QString::fromUtf8("\uE1D9")},
        {"signal_wifi_2_bar", QString::fromUtf8("\uE1D8")},
        {"signal_wifi_3_bar", QString::fromUtf8("\uE1D7")},
        {"signal_wifi_4_bar", QString::fromUtf8("\uE1D6")},
        {"wifi", QString::fromUtf8("\uE63E")},
        {"wifi_find", QString::fromUtf8("\uEE67")},
        {"wifi_off", QString::fromUtf8("\uE648")},
    };
    return icons.value(name, "?");
}

QString signalGlyph(int signal) {
    if (signal >= 80) return materialGlyph("signal_wifi_4_bar");
    if (signal >= 60) return materialGlyph("signal_wifi_3_bar");
    if (signal >= 35) return materialGlyph("signal_wifi_2_bar");
    if (signal > 0) return materialGlyph("signal_wifi_1_bar");
    return materialGlyph("signal_wifi_0_bar");
}

QString unescapeNmcli(QString value) {
    return value.replace("\\:", ":").trimmed();
}

struct ThemePalette {
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
};

ThemePalette loadTheme() {
    ThemePalette palette;
    QFile file(paletteFilePath());
    if (!file.open(QIODevice::ReadOnly)) {
        return palette;
    }
    const QJsonObject obj = QJsonDocument::fromJson(file.readAll()).object();
    if (!obj.value("use_matugen").toBool(false)) {
        return palette;
    }
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
    return palette;
}

struct WifiNetwork {
    QString ssid;
    int signal = 0;
    QString security = "--";
    bool inUse = false;

    bool secure() const {
        return !security.isEmpty() && security != "--";
    }
};

QList<WifiNetwork> parseNetworks(const QString &output) {
    QList<WifiNetwork> rows;
    QSet<QString> seen;
    const QStringList lines = output.split('\n', Qt::SkipEmptyParts);
    for (const QString &line : lines) {
        QStringList parts = line.split(':');
        if (parts.size() < 4) {
            continue;
        }
        WifiNetwork network;
        network.inUse = parts.value(0).trimmed() == "*";
        network.ssid = unescapeNmcli(parts.value(1));
        if (network.ssid.isEmpty() || seen.contains(network.ssid)) {
            continue;
        }
        seen.insert(network.ssid);
        bool ok = false;
        network.signal = parts.value(2).trimmed().toInt(&ok);
        if (!ok) {
            network.signal = 0;
        }
        network.security = unescapeNmcli(parts.mid(3).join(":"));
        if (network.security.isEmpty()) {
            network.security = "--";
        }
        rows.append(network);
    }
    std::sort(rows.begin(), rows.end(), [](const WifiNetwork &left, const WifiNetwork &right) {
        if (left.inUse != right.inUse) {
            return left.inUse;
        }
        if (left.signal != right.signal) {
            return left.signal > right.signal;
        }
        return left.ssid.toLower() < right.ssid.toLower();
    });
    return rows;
}

QString currentSsid() {
    const QString deviceStatus = runCommandText({"nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"}, 4000);
    const QStringList deviceLines = deviceStatus.split('\n', Qt::SkipEmptyParts);
    for (const QString &line : deviceLines) {
        const QStringList parts = line.split(':');
        if (parts.size() < 4) {
            continue;
        }
        if (parts.value(1).trimmed() == "wifi" && parts.value(2).trimmed().startsWith("connected")) {
            const QString connection = unescapeNmcli(parts.mid(3).join(":"));
            if (!connection.isEmpty()) {
                return connection;
            }
        }
    }

    const QString output = runCommandText({"nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"}, 4000);
    const QStringList lines = output.split('\n', Qt::SkipEmptyParts);
    for (const QString &line : lines) {
        if (line.startsWith("yes:")) {
            return unescapeNmcli(line.section(':', 1));
        }
    }
    return {};
}

bool radioEnabled() {
    return runCommandText({"nmcli", "radio", "wifi"}, 3000).trimmed().toLower() == "enabled";
}

QString activeWifiConnectionName() {
    const QString current = runCommandText({"nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"}, 4000);
    const QStringList lines = current.split('\n', Qt::SkipEmptyParts);
    for (const QString &line : lines) {
        if (line.endsWith(":802-11-wireless")) {
            return line.section(':', 0, 0).trimmed();
        }
    }
    return {};
}

}  // namespace

class WifiBackend final : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap palette READ palette NOTIFY paletteChanged)
    Q_PROPERTY(QVariantList networks READ networks NOTIFY networksChanged)
    Q_PROPERTY(QString currentConnectionLabel READ currentConnectionLabel NOTIFY summaryChanged)
    Q_PROPERTY(QString currentConnectionMeta READ currentConnectionMeta NOTIFY summaryChanged)
    Q_PROPERTY(QString currentConnectionIcon READ currentConnectionIcon NOTIFY summaryChanged)
    Q_PROPERTY(QString radioButtonText READ radioButtonText NOTIFY summaryChanged)
    Q_PROPERTY(QString selectedSsid READ selectedSsid NOTIFY selectionChanged)
    Q_PROPERTY(QString selectionHint READ selectionHint NOTIFY selectionChanged)
    Q_PROPERTY(bool selectedSecure READ selectedSecure NOTIFY selectionChanged)
    Q_PROPERTY(bool selectedInUse READ selectedInUse NOTIFY selectionChanged)
    Q_PROPERTY(QString connectButtonText READ connectButtonText NOTIFY selectionChanged)
    Q_PROPERTY(QString statusText READ statusText NOTIFY statusChanged)
    Q_PROPERTY(bool busy READ busy NOTIFY busyChanged)
    Q_PROPERTY(QString materialFontFamily READ materialFontFamily CONSTANT)
    Q_PROPERTY(QString uiFontFamily READ uiFontFamily CONSTANT)

public:
    explicit WifiBackend(QObject *parent = nullptr)
        : QObject(parent) {
        refreshPalette();
        QTimer::singleShot(0, this, &WifiBackend::refreshNetworks);
        connect(&themeTimer_, &QTimer::timeout, this, &WifiBackend::refreshPaletteIfNeeded);
        themeTimer_.start(15000);
    }

    ~WifiBackend() override {
        if (scanProcess_ != nullptr) {
            scanProcess_->kill();
            scanProcess_->waitForFinished(1000);
        }
        if (actionProcess_ != nullptr) {
            actionProcess_->kill();
            actionProcess_->waitForFinished(1000);
        }
    }

    QVariantMap palette() const { return palette_; }
    QVariantList networks() const { return networks_; }
    QString currentConnectionLabel() const { return currentConnectionLabel_; }
    QString currentConnectionMeta() const { return currentConnectionMeta_; }
    QString currentConnectionIcon() const { return currentConnectionIcon_; }
    QString radioButtonText() const { return radioButtonText_; }
    QString selectedSsid() const { return selectedSsid_; }
    QString selectionHint() const { return selectionHint_; }
    bool selectedSecure() const { return selectedSecure_; }
    bool selectedInUse() const { return selectedInUse_; }
    QString connectButtonText() const { return selectedInUse_ ? "Reconnect" : "Connect"; }
    QString statusText() const { return statusText_; }
    bool busy() const { return busy_; }
    QString materialFontFamily() const { return "Material Icons"; }
    QString uiFontFamily() const { return "Inter"; }

    Q_INVOKABLE QString glyph(const QString &name) const {
        return materialGlyph(name);
    }

    Q_INVOKABLE QVariantMap popupGeometry(int width, int height) const {
        Q_UNUSED(height);
        QScreen *screen = QGuiApplication::screenAt(QCursor::pos());
        if (screen == nullptr) {
            screen = QGuiApplication::primaryScreen();
        }
        const QRect area = screen ? screen->availableGeometry() : QRect(0, 0, 1280, 720);
        return {
            {"x", area.x() + area.width() - width - 18},
            {"y", area.y() + 52},
        };
    }

    Q_INVOKABLE void refreshNetworks() {
        if (busy_) {
            return;
        }
        setBusy(true);
        setStatusText("Refreshing Wi-Fi scan...");
        scanProcess_ = new QProcess(this);
        connect(scanProcess_, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this, [this](int, QProcess::ExitStatus) {
            const QString output = QString::fromUtf8(scanProcess_->readAllStandardOutput()).trimmed();
            const QString error = QString::fromUtf8(scanProcess_->readAllStandardError()).trimmed();
            scanProcess_->deleteLater();
            scanProcess_ = nullptr;
            setBusy(false);
            if (!error.isEmpty() && output.isEmpty()) {
                setStatusText(error);
                return;
            }
            applyNetworks(parseNetworks(output));
        });
        connect(scanProcess_, &QProcess::errorOccurred, this, [this](QProcess::ProcessError) {
            if (scanProcess_ != nullptr) {
                scanProcess_->deleteLater();
                scanProcess_ = nullptr;
            }
            setBusy(false);
            setStatusText("Failed to scan networks.");
        });
        scanProcess_->start("nmcli", {"-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "auto"});
    }

    Q_INVOKABLE void selectNetwork(const QString &ssid) {
        for (const WifiNetwork &network : networkCache_) {
            if (network.ssid == ssid) {
                setSelectedNetwork(network);
                return;
            }
        }
    }

    Q_INVOKABLE void connectSelected(const QString &password) {
        if (selectedSsid_.isEmpty()) {
            setStatusText("Select a network first.");
            return;
        }
        const QString trimmedPassword = password.trimmed();
        if (selectedSecure_ && !selectedInUse_ && trimmedPassword.isEmpty()) {
            setStatusText("Enter the Wi-Fi password for this secured network.");
            return;
        }
        QStringList command = {"nmcli", "dev", "wifi", "connect", selectedSsid_};
        if (!trimmedPassword.isEmpty()) {
            command << "password" << trimmedPassword;
        }
        runAction(command, QStringLiteral("Connected to %1").arg(selectedSsid_));
    }

    Q_INVOKABLE void disconnectCurrent() {
        const QString wifiName = activeWifiConnectionName();
        if (wifiName.isEmpty()) {
            setStatusText("Wi-Fi already disconnected.");
            return;
        }
        runAction({"nmcli", "connection", "down", "id", wifiName}, "Wi-Fi disconnected.");
    }

    Q_INVOKABLE void toggleRadio() {
        const bool nextEnabled = !radioEnabled();
        runAction({"nmcli", "radio", "wifi", nextEnabled ? "on" : "off"}, QStringLiteral("Wi-Fi radio turned %1.").arg(nextEnabled ? "on" : "off"));
    }

    Q_INVOKABLE void closeWindow() {
        QGuiApplication::quit();
    }

signals:
    void paletteChanged();
    void networksChanged();
    void summaryChanged();
    void selectionChanged();
    void statusChanged();
    void busyChanged();

private:
    void refreshPaletteIfNeeded() {
        const QFileInfo info(paletteFilePath());
        const QDateTime modified = info.exists() ? info.lastModified() : QDateTime();
        if (modified.isValid() && modified == paletteLastModified_) {
            return;
        }
        refreshPalette();
    }

    void refreshPalette() {
        const ThemePalette theme = loadTheme();
        const QVariantMap nextPalette = {
            {"panelBg", rgba(theme.surfaceContainer, 0.94)},
            {"panelBorder", rgba(theme.outline, 0.20)},
            {"cardBg", rgba(theme.surfaceContainerHigh, 0.90)},
            {"cardAltBg", rgba(theme.surfaceContainerHigh, 0.82)},
            {"text", theme.onSurface},
            {"textMuted", rgba(theme.onSurfaceVariant, 0.78)},
            {"icon", theme.onSurface},
            {"primary", theme.primary},
            {"primaryContainer", theme.primaryContainer},
            {"onPrimary", theme.onPrimary},
            {"onPrimaryContainer", theme.onPrimaryContainer},
            {"hoverBg", rgba(theme.primary, 0.14)},
            {"runningBg", rgba(theme.onSurface, 0.06)},
            {"runningBorder", rgba(theme.outline, 0.16)},
            {"buttonMutedBg", rgba(theme.surfaceContainerHigh, 0.86)},
            {"inputBg", rgba(theme.surfaceContainer, 0.76)},
            {"scrollHandle", rgba(theme.primary, 0.30)},
            {"shadow", rgba("#000000", 0.38)},
            {"danger", "#FFB4AB"},
            {"dangerBg", rgba("#FFB4AB", 0.16)},
            {"dangerBorder", rgba("#FFB4AB", 0.30)},
            {"accentButtonBg", rgba(theme.primaryContainer, 0.92)},
            {"accentButtonBorder", rgba(theme.primary, 0.22)},
            {"heroGlow", rgba(blend(theme.primary, theme.secondary, 0.35), 0.20)},
        };
        const QFileInfo info(paletteFilePath());
        paletteLastModified_ = info.exists() ? info.lastModified() : QDateTime();
        if (palette_ == nextPalette) {
            return;
        }
        palette_ = nextPalette;
        emit paletteChanged();
    }

    void applyNetworks(const QList<WifiNetwork> &networks) {
        networkCache_ = networks;
        const QString current = currentSsid();
        const bool enabled = radioEnabled();

        currentConnectionLabel_ =
            (!current.isEmpty() && current != "Disconnected")
                ? QStringLiteral("Connected to %1").arg(current)
                : QStringLiteral("Wi-Fi not connected");
        currentConnectionMeta_ = "Scanning adapter state and active SSID.";
        currentConnectionIcon_ = materialGlyph((!current.isEmpty() && enabled) ? "wifi" : "wifi_off");
        radioButtonText_ = enabled ? "Turn Wi-Fi Off" : "Turn Wi-Fi On";
        emit summaryChanged();

        QVariantList items;
        for (const WifiNetwork &network : networkCache_) {
            items.append(QVariantMap{
                {"ssid", network.ssid},
                {"signal", network.signal},
                {"security", network.security},
                {"inUse", network.inUse},
                {"secure", network.secure()},
                {"signalGlyph", network.signal > 0 ? signalGlyph(network.signal) : materialGlyph("wifi_find")},
                {"trailGlyph", materialGlyph(network.inUse ? "check_circle" : (network.secure() ? "lock" : "lock_open"))},
                {"detail", network.inUse ? "Connected" : QStringLiteral("%1%% signal%2").arg(network.signal).arg(network.secure() ? " • secured" : "")},
            });
        }
        networks_ = items;
        emit networksChanged();

        if (networkCache_.isEmpty()) {
            clearSelection();
            setStatusText("No Wi-Fi networks were found. Try turning the radio on or refreshing the scan.");
            return;
        }

        WifiNetwork selection = networkCache_.constFirst();
        for (const WifiNetwork &network : networkCache_) {
            if (network.ssid == selectedSsid_) {
                selection = network;
                break;
            }
            if (network.inUse) {
                selection = network;
            }
        }
        setSelectedNetwork(selection);
        setStatusText(QStringLiteral("%1 network(s) available").arg(networkCache_.size()));
    }

    void clearSelection() {
        selectedSsid_.clear();
        selectedSecure_ = false;
        selectedInUse_ = false;
        selectionHint_ = "Choose a Wi-Fi network below. Password is only needed for secured SSIDs.";
        emit selectionChanged();
    }

    void setSelectedNetwork(const WifiNetwork &network) {
        selectedSsid_ = network.ssid;
        selectedSecure_ = network.secure();
        selectedInUse_ = network.inUse;
        if (network.inUse) {
            selectionHint_ = "Currently connected. You can disconnect or reconnect.";
        } else if (network.secure()) {
            selectionHint_ = "Secured network. Enter the password to connect if this network is not saved yet.";
        } else {
            selectionHint_ = "Open network. No password is required.";
        }
        emit selectionChanged();
    }

    void runAction(const QStringList &command, const QString &successMessage) {
        if (busy_) {
            return;
        }
        setBusy(true);
        setStatusText("Applying Wi-Fi change...");
        actionProcess_ = new QProcess(this);
        connect(actionProcess_, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this, [this, successMessage](int exitCode, QProcess::ExitStatus) {
            const QString stdoutText = QString::fromUtf8(actionProcess_->readAllStandardOutput()).trimmed();
            const QString stderrText = QString::fromUtf8(actionProcess_->readAllStandardError()).trimmed();
            actionProcess_->deleteLater();
            actionProcess_ = nullptr;
            setBusy(false);
            if (exitCode == 0) {
                setStatusText(successMessage);
                QTimer::singleShot(400, this, &WifiBackend::refreshNetworks);
                return;
            }
            setStatusText(!stderrText.isEmpty() ? stderrText : (!stdoutText.isEmpty() ? stdoutText : "Wi-Fi action failed."));
        });
        connect(actionProcess_, &QProcess::errorOccurred, this, [this](QProcess::ProcessError) {
            if (actionProcess_ != nullptr) {
                actionProcess_->deleteLater();
                actionProcess_ = nullptr;
            }
            setBusy(false);
            setStatusText("Failed to start Wi-Fi action.");
        });
        actionProcess_->start(command.first(), command.mid(1));
    }

    void setStatusText(const QString &value) {
        if (statusText_ == value) {
            return;
        }
        statusText_ = value;
        emit statusChanged();
    }

    void setBusy(bool value) {
        if (busy_ == value) {
            return;
        }
        busy_ = value;
        emit busyChanged();
    }

    QVariantMap palette_;
    QVariantList networks_;
    QList<WifiNetwork> networkCache_;
    QString currentConnectionLabel_ = "Checking current network...";
    QString currentConnectionMeta_ = "Scanning adapter state and active SSID.";
    QString currentConnectionIcon_ = materialGlyph("wifi");
    QString radioButtonText_ = "Turn Wi-Fi Off";
    QString selectedSsid_;
    QString selectionHint_ = "Choose a Wi-Fi network below. Password is only needed for secured SSIDs.";
    bool selectedSecure_ = false;
    bool selectedInUse_ = false;
    QString statusText_ = "Scanning available networks...";
    bool busy_ = false;
    QTimer themeTimer_;
    QDateTime paletteLastModified_;
    QProcess *scanProcess_ = nullptr;
    QProcess *actionProcess_ = nullptr;
};

int main(int argc, char *argv[]) {
    QGuiApplication app(argc, argv);
    app.setApplicationName("Hanauta Wi-Fi Control");
    app.setDesktopFileName("HanautaWifiControl");
    QQuickStyle::setStyle("Basic");
    loadFonts();

    const QString qmlPath = repoRoot() + "/src/service/hanauta-wifi-control.qml";
    if (!QFile::exists(qmlPath)) {
        fprintf(stderr, "ERROR: QML file not found: %s\n", qPrintable(qmlPath));
        return 2;
    }

    WifiBackend backend;
    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty("backend", &backend);
    engine.load(QUrl::fromLocalFile(qmlPath));
    if (engine.rootObjects().isEmpty()) {
        fprintf(stderr, "ERROR: failed to load QML (no root objects).\n");
        return 3;
    }
    return app.exec();
}

#include "hanauta-wifi-control.moc"
