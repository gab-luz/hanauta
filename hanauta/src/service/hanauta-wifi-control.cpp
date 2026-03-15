#include <QCoreApplication>
#include <QCursor>
#include <QDir>
#include <QFile>
#include <QFontDatabase>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMap>
#include <QPointer>
#include <QProcess>
#include <QQuickStyle>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QRegularExpression>
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

QString networkScriptPath() {
    return repoRoot() + "/src/eww/scripts/network.sh";
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
        root + "/assets/fonts/Outfit-VariableFont_wght.ttf",
        root + "/assets/fonts/MaterialIcons-Regular.ttf",
        root + "/assets/fonts/MaterialIconsOutlined-Regular.otf",
        root + "/assets/fonts/MaterialSymbolsOutlined.ttf",
        root + "/assets/fonts/MaterialSymbolsRounded.ttf",
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
        {"lock", QString::fromUtf8("\uE897")},
        {"lock_open", QString::fromUtf8("\uE898")},
        {"refresh", QString::fromUtf8("\uE5D5")},
        {"router", QString::fromUtf8("\uE328")},
        {"settings_ethernet", QString::fromUtf8("\uF017")},
        {"signal_wifi_0_bar", QString::fromUtf8("\uE1DA")},
        {"signal_wifi_1_bar", QString::fromUtf8("\uE1D9")},
        {"signal_wifi_2_bar", QString::fromUtf8("\uE1D8")},
        {"signal_wifi_3_bar", QString::fromUtf8("\uE1D7")},
        {"signal_wifi_4_bar", QString::fromUtf8("\uE1D6")},
        {"wifi", QString::fromUtf8("\uE63E")},
        {"wifi_find", QString::fromUtf8("\uEE67")},
        {"wifi_off", QString::fromUtf8("\uE648")},
        {"close", QString::fromUtf8("\uE5CD")},
    };
    return icons.value(name, "?");
}

QString wifiSignalGlyph(int signal) {
    if (signal >= 80) return "signal_wifi_4_bar";
    if (signal >= 60) return "signal_wifi_3_bar";
    if (signal >= 35) return "signal_wifi_2_bar";
    if (signal > 0) return "signal_wifi_1_bar";
    return "signal_wifi_0_bar";
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
    bool secure = false;
};

QList<WifiNetwork> parseNetworkList(const QString &output) {
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
        network.secure = network.security != "--";
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
    const QString output = runCommandText({"nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"}, 4000);
    const QStringList lines = output.split('\n', Qt::SkipEmptyParts);
    for (const QString &line : lines) {
        if (line.startsWith("yes:")) {
            return unescapeNmcli(line.section(':', 1));
        }
    }
    const QString script = networkScriptPath();
    if (QFile::exists(script)) {
        return runCommandText({script, "ssid"}, 4000);
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
    Q_PROPERTY(QString monoFontFamily READ monoFontFamily CONSTANT)

public:
    explicit WifiBackend(QObject *parent = nullptr)
        : QObject(parent) {
        refreshPalette();
        refreshNetworks();
        connect(&themeTimer_, &QTimer::timeout, this, &WifiBackend::refreshPalette);
        themeTimer_.start(3000);
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
    QString monoFontFamily() const { return "JetBrains Mono"; }

    Q_INVOKABLE QString glyph(const QString &name) const {
        return materialGlyph(name);
    }

    Q_INVOKABLE QVariantMap popupGeometry(int width, int height) const {
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
        QString program = QStandardPaths::findExecutable("nmcli");
        if (program.isEmpty()) {
            setBusy(false);
            setStatusText("nmcli was not found.");
            return;
        }
        scanProcess_ = new QProcess(this);
        connect(scanProcess_, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this, [this](int, QProcess::ExitStatus) {
            const QString output = QString::fromUtf8(scanProcess_->readAllStandardOutput());
            const QList<WifiNetwork> parsed = parseNetworkList(output);
            applyScan(parsed);
            scanProcess_->deleteLater();
            scanProcess_ = nullptr;
            setBusy(false);
        });
        connect(scanProcess_, &QProcess::errorOccurred, this, [this](QProcess::ProcessError) {
            setBusy(false);
            setStatusText("Failed to scan networks.");
            if (scanProcess_ != nullptr) {
                scanProcess_->deleteLater();
                scanProcess_ = nullptr;
            }
        });
        scanProcess_->start(program, {"-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "auto"});
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
        runAction({"nmcli", "dev", "wifi", "connect", selectedSsid_, trimmedPassword.isEmpty() ? QString() : "password", trimmedPassword}, true, QStringLiteral("Connected to %1").arg(selectedSsid_));
    }

    Q_INVOKABLE void disconnectCurrent() {
        const QString wifiName = activeWifiConnectionName();
        if (wifiName.isEmpty()) {
            setStatusText("Wi-Fi already disconnected.");
            return;
        }
        runAction({"nmcli", "connection", "down", "id", wifiName}, true, "Wi-Fi disconnected.");
    }

    Q_INVOKABLE void toggleRadio() {
        const bool nextEnabled = !radioEnabled();
        runAction({"nmcli", "radio", "wifi", nextEnabled ? "on" : "off"}, true, QStringLiteral("Wi-Fi radio turned %1.").arg(nextEnabled ? "on" : "off"));
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
    void refreshPalette() {
        const ThemePalette theme = loadTheme();
        palette_ = {
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
            {"heroGlow", rgba(blend(theme.primary, theme.secondary, 0.35), 0.20)},
        };
        emit paletteChanged();
    }

    void applyScan(const QList<WifiNetwork> &parsed) {
        networkCache_ = parsed;
        const QString current = currentSsid();
        const bool enabled = radioEnabled();

        currentConnectionLabel_ =
            (!current.isEmpty() && current != "Disconnected")
                ? QStringLiteral("Connected to %1").arg(current)
                : QStringLiteral("Wi-Fi not connected");
        currentConnectionMeta_ = "Scanning adapter state and active SSID.";
        currentConnectionIcon_ = materialGlyph((!current.isEmpty() && enabled) ? "wifi" : "wifi_off");
        radioButtonText_ = enabled ? "Turn Wi-Fi Off" : "Turn Wi-Fi On";

        QVariantList items;
        for (const WifiNetwork &network : networkCache_) {
            items.append(QVariantMap{
                {"ssid", network.ssid},
                {"signal", network.signal},
                {"security", network.security},
                {"inUse", network.inUse},
                {"secure", network.secure},
                {"signalGlyph", materialGlyph(network.signal > 0 ? wifiSignalGlyph(network.signal) : "wifi_find")},
                {"trailGlyph", materialGlyph(network.inUse ? "check_circle" : (network.secure ? "lock" : "lock_open"))},
                {"detail", network.inUse ? "Connected" : QStringLiteral("%1%% signal%2").arg(network.signal).arg(network.secure ? " • secured" : "")},
            });
        }
        networks_ = items;
        emit networksChanged();
        emit summaryChanged();

        if (networkCache_.isEmpty()) {
            clearSelection();
            setStatusText("No Wi-Fi networks were found. Try turning the radio on or refreshing the scan.");
            return;
        }

        WifiNetwork nextSelection;
        bool found = false;
        for (const WifiNetwork &network : networkCache_) {
            if (network.ssid == selectedSsid_) {
                nextSelection = network;
                found = true;
                break;
            }
        }
        if (!found) {
            nextSelection = std::find_if(networkCache_.begin(), networkCache_.end(), [](const WifiNetwork &network) {
                return network.inUse;
            }) != networkCache_.end()
                ? *std::find_if(networkCache_.begin(), networkCache_.end(), [](const WifiNetwork &network) { return network.inUse; })
                : networkCache_.constFirst();
        }
        setSelectedNetwork(nextSelection);
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
        selectedSecure_ = network.secure;
        selectedInUse_ = network.inUse;
        if (network.inUse) {
            selectionHint_ = "Currently connected. You can disconnect or reconnect.";
        } else if (network.secure) {
            selectionHint_ = "Secured network. Enter the password to connect if this network is not saved yet.";
        } else {
            selectionHint_ = "Open network. No password is required.";
        }
        emit selectionChanged();
    }

    void runAction(QStringList command, bool refreshAfter, const QString &successMessage) {
        command.removeAll(QString());
        if (busy_) {
            return;
        }
        setBusy(true);
        setStatusText("Applying Wi-Fi change...");
        QString program = QStandardPaths::findExecutable(command.value(0));
        if (program.isEmpty()) {
            setBusy(false);
            setStatusText("nmcli was not found.");
            return;
        }
        actionProcess_ = new QProcess(this);
        connect(actionProcess_, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this, [this, refreshAfter, successMessage](int exitCode, QProcess::ExitStatus) {
            const QString stderrText = QString::fromUtf8(actionProcess_->readAllStandardError()).trimmed();
            const QString stdoutText = QString::fromUtf8(actionProcess_->readAllStandardOutput()).trimmed();
            const bool ok = exitCode == 0;
            setBusy(false);
            setStatusText(ok ? successMessage : (!stderrText.isEmpty() ? stderrText : (!stdoutText.isEmpty() ? stdoutText : "Wi-Fi action failed.")));
            actionProcess_->deleteLater();
            actionProcess_ = nullptr;
            if (ok && refreshAfter) {
                QTimer::singleShot(400, this, &WifiBackend::refreshNetworks);
            }
        });
        connect(actionProcess_, &QProcess::errorOccurred, this, [this](QProcess::ProcessError) {
            setBusy(false);
            setStatusText("Failed to start Wi-Fi action.");
            if (actionProcess_ != nullptr) {
                actionProcess_->deleteLater();
                actionProcess_ = nullptr;
            }
        });
        actionProcess_->start(program, command.mid(1));
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
