#include <QColor>
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QFontDatabase>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QProcess>
#include <QRegularExpression>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QStandardPaths>
#include <QStringList>
#include <QTimer>
#include <QUrl>

#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <pwd.h>
#include <sys/types.h>
#include <unistd.h>

namespace {

struct ThemePalette {
    bool useMatugen = false;
    QString primary = "#D0BCFF";
    QString onPrimary = "#381E72";
    QString primaryContainer = "#4F378B";
    QString secondary = "#CCC2DC";
    QString tertiary = "#EFB8C8";
    QString surfaceContainer = "#211F26";
    QString surfaceContainerHigh = "#2B2930";
    QString onSurface = "#E6E0E9";
    QString onSurfaceVariant = "#CAC4D0";
    QString outline = "#938F99";
    QString error = "#F2B8B5";
    QString onError = "#601410";
};

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

QString rgba(const QString &hex, double alpha) {
    const QColor color(normalizeHex(hex, "#000000"));
    return QStringLiteral("rgba(%1, %2, %3, %4)")
        .arg(color.red())
        .arg(color.green())
        .arg(color.blue())
        .arg(QString::number(std::clamp(alpha, 0.0, 1.0), 'f', 2));
}

QString blend(const QString &leftHex, const QString &rightHex, double ratio) {
    const QColor left(normalizeHex(leftHex, "#000000"));
    const QColor right(normalizeHex(rightHex, "#000000"));
    const double t = std::clamp(ratio, 0.0, 1.0);
    const int red = static_cast<int>(left.red() + (right.red() - left.red()) * t);
    const int green = static_cast<int>(left.green() + (right.green() - left.green()) * t);
    const int blue = static_cast<int>(left.blue() + (right.blue() - left.blue()) * t);
    return QStringLiteral("#%1%2%3")
        .arg(red, 2, 16, QLatin1Char('0'))
        .arg(green, 2, 16, QLatin1Char('0'))
        .arg(blue, 2, 16, QLatin1Char('0'))
        .toUpper();
}

QString homeDir() {
    return QDir::homePath();
}

QString settingsFilePath() {
    return homeDir() + "/.local/state/hanauta/notification-center/settings.json";
}

QString paletteFilePath() {
    return homeDir() + "/.local/state/hanauta/theme/pyqt_palette.json";
}

QString commandPath(const QString &command) {
    return QStandardPaths::findExecutable(command);
}

QString currentUsername() {
    if (const char *envUser = std::getenv("USER"); envUser && *envUser) {
        return QString::fromUtf8(envUser);
    }
    if (passwd *pwd = getpwuid(getuid()); pwd && pwd->pw_name) {
        return QString::fromUtf8(pwd->pw_name);
    }
    return QStringLiteral("User");
}

int readUptimeSeconds() {
    QFile file("/proc/uptime");
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        return -1;
    }
    const QString first = QString::fromUtf8(file.readLine()).trimmed().split(' ').value(0);
    bool ok = false;
    const double seconds = first.toDouble(&ok);
    if (!ok) {
        return -1;
    }
    return static_cast<int>(seconds);
}

QString formatUptime(int seconds) {
    if (seconds < 0) {
        return QStringLiteral("unknown");
    }
    const int days = seconds / 86400;
    const int remAfterDays = seconds % 86400;
    const int hours = remAfterDays / 3600;
    const int minutes = (remAfterDays % 3600) / 60;
    QStringList parts;
    if (days > 0) {
        parts << QStringLiteral("%1 day%2").arg(days).arg(days == 1 ? "" : "s");
    }
    if (hours > 0) {
        parts << QStringLiteral("%1 hour%2").arg(hours).arg(hours == 1 ? "" : "s");
    }
    if (parts.isEmpty()) {
        parts << QStringLiteral("%1 minute%2").arg(minutes).arg(minutes == 1 ? "" : "s");
    }
    return parts.join(", ");
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

bool startDetachedCommand(const QStringList &command) {
    if (command.isEmpty()) {
        return false;
    }
    QString executable = command.first();
    if (!QFileInfo::exists(executable)) {
        executable = commandPath(executable);
    }
    if (executable.isEmpty()) {
        return false;
    }
    return QProcess::startDetached(executable, command.mid(1));
}

void terminateBackgroundMatches(const QString &pattern) {
    QProcess::execute("pkill", {"-f", pattern});
}

QJsonObject loadJsonObject(const QString &path) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        return {};
    }
    const QJsonDocument doc = QJsonDocument::fromJson(file.readAll());
    if (!doc.isObject()) {
        return {};
    }
    return doc.object();
}

bool saveJsonObject(const QString &path, const QJsonObject &object) {
    const QFileInfo info(path);
    QDir().mkpath(info.absolutePath());
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        return false;
    }
    file.write(QJsonDocument(object).toJson(QJsonDocument::Indented));
    return true;
}

ThemePalette loadThemePalette() {
    ThemePalette palette;
    const QJsonObject obj = loadJsonObject(paletteFilePath());
    if (!obj.value("use_matugen").toBool(false)) {
        return palette;
    }
    palette.useMatugen = true;
    palette.primary = normalizeHex(obj.value("primary").toString(palette.primary), palette.primary);
    palette.onPrimary = normalizeHex(obj.value("on_primary").toString(palette.onPrimary), palette.onPrimary);
    palette.primaryContainer = normalizeHex(obj.value("primary_container").toString(palette.primaryContainer), palette.primaryContainer);
    palette.secondary = normalizeHex(obj.value("secondary").toString(palette.secondary), palette.secondary);
    palette.tertiary = normalizeHex(obj.value("tertiary").toString(palette.tertiary), palette.tertiary);
    palette.surfaceContainer = normalizeHex(obj.value("surface_container").toString(palette.surfaceContainer), palette.surfaceContainer);
    palette.surfaceContainerHigh = normalizeHex(obj.value("surface_container_high").toString(palette.surfaceContainerHigh), palette.surfaceContainerHigh);
    palette.onSurface = normalizeHex(obj.value("on_surface").toString(palette.onSurface), palette.onSurface);
    palette.onSurfaceVariant = normalizeHex(obj.value("on_surface_variant").toString(palette.onSurfaceVariant), palette.onSurfaceVariant);
    palette.outline = normalizeHex(obj.value("outline").toString(palette.outline), palette.outline);
    palette.error = normalizeHex(obj.value("error").toString(palette.error), palette.error);
    palette.onError = normalizeHex(obj.value("on_error").toString(palette.onError), palette.onError);
    return palette;
}

QJsonObject defaultAppearance() {
    return {
        {"accent", "orchid"},
        {"transparency", true},
        {"notification_center_panel_opacity", 84},
        {"notification_center_card_opacity", 92},
    };
}

int clampOpacityPercent(int value) {
    return std::clamp(value, 35, 100);
}

QJsonObject defaultService(const QString &key) {
    if (key == "home_assistant") {
        return {{"enabled", true}, {"show_in_notification_center", true}};
    }
    if (key == "vpn_control") {
        return {{"enabled", true}, {"show_in_notification_center", false}};
    }
    if (key == "christian_widget") {
        return {{"enabled", false}, {"show_in_notification_center", false}};
    }
    if (key == "calendar_widget") {
        return {{"enabled", true}, {"show_in_notification_center", false}};
    }
    if (key == "reminders_widget") {
        return {{"enabled", false}, {"show_in_notification_center", false}};
    }
    if (key == "pomodoro_widget") {
        return {{"enabled", true}, {"show_in_notification_center", true}};
    }
    if (key == "rss_widget") {
        return {{"enabled", true}, {"show_in_notification_center", true}};
    }
    if (key == "obs_widget") {
        return {{"enabled", true}, {"show_in_notification_center", true}};
    }
    if (key == "crypto_widget") {
        return {{"enabled", true}, {"show_in_notification_center", true}};
    }
    if (key == "vps_widget") {
        return {{"enabled", false}, {"show_in_notification_center", true}};
    }
    if (key == "desktop_clock_widget") {
        return {{"enabled", false}, {"show_in_notification_center", true}};
    }
    if (key == "game_mode") {
        return {{"enabled", false}, {"show_in_notification_center", true}};
    }
    return {{"enabled", false}, {"show_in_notification_center", false}};
}

QStringList serviceKeys() {
    return {
        "home_assistant",
        "vpn_control",
        "christian_widget",
        "calendar_widget",
        "reminders_widget",
        "pomodoro_widget",
        "rss_widget",
        "obs_widget",
        "crypto_widget",
        "vps_widget",
        "desktop_clock_widget",
        "game_mode",
    };
}

QJsonObject mergedSettings() {
    QJsonObject root = loadJsonObject(settingsFilePath());
    QJsonObject appearance = root.value("appearance").toObject();
    if (appearance.isEmpty()) {
        appearance = defaultAppearance();
    }
    if (appearance.value("accent").toString().trimmed().isEmpty()) {
        appearance.insert("accent", "orchid");
    }
    if (!appearance.contains("transparency")) {
        appearance.insert("transparency", true);
    }
    const int panelOpacity = clampOpacityPercent(
        appearance.value("notification_center_panel_opacity").toInt(84)
    );
    int cardOpacity = clampOpacityPercent(
        appearance.value("notification_center_card_opacity").toInt(92)
    );
    if (cardOpacity < panelOpacity) {
        cardOpacity = panelOpacity;
    }
    appearance.insert("notification_center_panel_opacity", panelOpacity);
    appearance.insert("notification_center_card_opacity", cardOpacity);
    root.insert("appearance", appearance);

    QJsonObject ha = root.value("home_assistant").toObject();
    if (!ha.contains("url")) {
        ha.insert("url", "");
    }
    if (!ha.contains("token")) {
        ha.insert("token", "");
    }
    QJsonArray pinned = ha.value("pinned_entities").toArray();
    QJsonArray normalizedPinned;
    for (const QJsonValue &value : pinned) {
        if (value.isString() && normalizedPinned.size() < 5) {
            normalizedPinned.append(value.toString());
        }
    }
    ha.insert("pinned_entities", normalizedPinned);
    root.insert("home_assistant", ha);

    QJsonObject services = root.value("services").toObject();
    for (const QString &key : serviceKeys()) {
        QJsonObject defaults = defaultService(key);
        QJsonObject current = services.value(key).toObject();
        if (!current.contains("enabled")) {
            current.insert("enabled", defaults.value("enabled").toBool());
        }
        if (!current.contains("show_in_notification_center")) {
            current.insert("show_in_notification_center", defaults.value("show_in_notification_center").toBool());
        }
        services.insert(key, current);
    }
    root.insert("services", services);
    return root;
}

bool serviceEnabled(const QJsonObject &settings, const QString &key) {
    return settings.value("services").toObject().value(key).toObject().value("enabled").toBool(true);
}

bool serviceVisible(const QJsonObject &settings, const QString &key) {
    const QJsonObject service = settings.value("services").toObject().value(key).toObject();
    return service.value("enabled").toBool(true) && service.value("show_in_notification_center").toBool(false);
}

void loadAppFonts(const QString &repoRoot) {
    const QStringList fonts = {
        repoRoot + "/assets/fonts/InterVariable.ttf",
        repoRoot + "/assets/fonts/Outfit-VariableFont_wght.ttf",
        repoRoot + "/assets/fonts/MaterialIcons-Regular.ttf",
        repoRoot + "/assets/fonts/MaterialIconsOutlined-Regular.otf",
        repoRoot + "/assets/fonts/MaterialSymbolsOutlined.ttf",
        repoRoot + "/assets/fonts/MaterialSymbolsRounded.ttf",
    };
    for (const QString &path : fonts) {
        if (QFile::exists(path)) {
            QFontDatabase::addApplicationFont(path);
        }
    }
}

QString formatMillis(int ms) {
    ms = std::max(0, ms);
    const int totalSeconds = ms / 1000;
    const int seconds = totalSeconds % 60;
    const int totalMinutes = totalSeconds / 60;
    const int minutes = totalMinutes % 60;
    const int hours = totalMinutes / 60;
    if (hours > 0) {
        return QStringLiteral("%1:%2:%3")
            .arg(hours)
            .arg(minutes, 2, 10, QLatin1Char('0'))
            .arg(seconds, 2, 10, QLatin1Char('0'));
    }
    return QStringLiteral("%1:%2")
        .arg(minutes)
        .arg(seconds, 2, 10, QLatin1Char('0'));
}

QString scriptOutput(const QString &repoRoot, const QString &scriptName, const QStringList &args = {}, int timeoutMs = 2000) {
    const QString path = repoRoot + "/src/eww/scripts/" + scriptName;
    if (!QFileInfo::exists(path)) {
        return {};
    }
    QStringList command{path};
    command.append(args);
    return runCommand(command, timeoutMs);
}

bool runScriptDetached(const QString &repoRoot, const QString &scriptName, const QStringList &args = {}) {
    const QString path = repoRoot + "/src/eww/scripts/" + scriptName;
    if (!QFileInfo::exists(path)) {
        return false;
    }
    QStringList command{path};
    command.append(args);
    return startDetachedCommand(command);
}

}  // namespace

class NotificationCenterBackend final : public QObject {
    Q_OBJECT
    Q_PROPERTY(QString username READ username NOTIFY usernameChanged)
    Q_PROPERTY(QString uptime READ uptime NOTIFY uptimeChanged)
    Q_PROPERTY(QString uiFontFamily READ uiFontFamily CONSTANT)
    Q_PROPERTY(QString materialFontFamily READ materialFontFamily CONSTANT)
    Q_PROPERTY(QString monoFontFamily READ monoFontFamily CONSTANT)
    Q_PROPERTY(QVariantMap palette READ palette NOTIFY paletteChanged)
    Q_PROPERTY(QVariantList quickSettings READ quickSettings NOTIFY quickSettingsChanged)
    Q_PROPERTY(int brightness READ brightness NOTIFY brightnessChanged)
    Q_PROPERTY(int volume READ volume NOTIFY volumeChanged)
    Q_PROPERTY(QString mediaTitle READ mediaTitle NOTIFY mediaChanged)
    Q_PROPERTY(QString mediaArtist READ mediaArtist NOTIFY mediaChanged)
    Q_PROPERTY(QString mediaStatus READ mediaStatus NOTIFY mediaChanged)
    Q_PROPERTY(QString mediaCover READ mediaCover NOTIFY mediaChanged)
    Q_PROPERTY(double mediaProgress READ mediaProgress NOTIFY mediaChanged)
    Q_PROPERTY(QString mediaElapsed READ mediaElapsed NOTIFY mediaChanged)
    Q_PROPERTY(QString mediaTotal READ mediaTotal NOTIFY mediaChanged)
    Q_PROPERTY(QVariantMap phoneInfo READ phoneInfo NOTIFY phoneInfoChanged)
    Q_PROPERTY(QVariantList serviceCards READ serviceCards NOTIFY serviceCardsChanged)
    Q_PROPERTY(QVariantList systemOverview READ systemOverview NOTIFY systemOverviewChanged)
    Q_PROPERTY(bool homeAssistantVisible READ homeAssistantVisible NOTIFY homeAssistantChanged)
    Q_PROPERTY(QVariantList homeAssistantTiles READ homeAssistantTiles NOTIFY homeAssistantChanged)
    Q_PROPERTY(QString homeAssistantStatus READ homeAssistantStatus NOTIFY homeAssistantChanged)
    Q_PROPERTY(QString accentName READ accentName NOTIFY settingsChanged)
    Q_PROPERTY(QString appearanceStatus READ appearanceStatus NOTIFY settingsChanged)
    Q_PROPERTY(QString haUrl READ haUrl NOTIFY settingsChanged)
    Q_PROPERTY(QString haToken READ haToken NOTIFY settingsChanged)
    Q_PROPERTY(QString haSettingsStatus READ haSettingsStatus NOTIFY settingsChanged)
    Q_PROPERTY(QVariantList haEntities READ haEntities NOTIFY settingsChanged)

public:
    explicit NotificationCenterBackend(const QString &repoRoot, QObject *parent = nullptr)
        : QObject(parent),
          repoRoot_(repoRoot),
          pyqtRoot_(repoRoot + "/src/pyqt"),
          binRoot_(repoRoot + "/bin") {
        reloadSettings();
        reloadTheme();

        brightnessCommitTimer_.setSingleShot(true);
        volumeCommitTimer_.setSingleShot(true);
        connect(&brightnessCommitTimer_, &QTimer::timeout, this, &NotificationCenterBackend::commitBrightness);
        connect(&volumeCommitTimer_, &QTimer::timeout, this, &NotificationCenterBackend::commitVolume);

        pollTimer_.setInterval(3500);
        connect(&pollTimer_, &QTimer::timeout, this, &NotificationCenterBackend::refreshAll);
        pollTimer_.start();

        themeTimer_.setInterval(3000);
        connect(&themeTimer_, &QTimer::timeout, this, &NotificationCenterBackend::reloadIfChanged);
        themeTimer_.start();

        mediaTimer_.setInterval(1000);
        connect(&mediaTimer_, &QTimer::timeout, this, &NotificationCenterBackend::pollMediaProgress);
        mediaTimer_.start();

        uptimeTimer_.setInterval(30000);
        connect(&uptimeTimer_, &QTimer::timeout, this, &NotificationCenterBackend::updateHeader);
        uptimeTimer_.start();

        connect(&network_, &QNetworkAccessManager::finished, this, &NotificationCenterBackend::onNetworkReplyFinished);

        refreshAll();
    }

    QString username() const { return username_; }
    QString uptime() const { return uptime_; }
    QString uiFontFamily() const { return QStringLiteral("Inter"); }
    QString materialFontFamily() const { return QStringLiteral("Material Icons"); }
    QString monoFontFamily() const { return QStringLiteral("JetBrains Mono"); }
    QVariantMap palette() const { return palette_; }
    QVariantList quickSettings() const { return quickSettings_; }
    int brightness() const { return brightness_; }
    int volume() const { return volume_; }
    QString mediaTitle() const { return mediaTitle_; }
    QString mediaArtist() const { return mediaArtist_; }
    QString mediaStatus() const { return mediaStatus_; }
    QString mediaCover() const { return mediaCover_; }
    double mediaProgress() const { return mediaProgress_; }
    QString mediaElapsed() const { return mediaElapsed_; }
    QString mediaTotal() const { return mediaTotal_; }
    QVariantMap phoneInfo() const { return phoneInfo_; }
    QVariantList serviceCards() const { return serviceCards_; }
    QVariantList systemOverview() const { return systemOverview_; }
    bool homeAssistantVisible() const { return serviceVisible(settings_, "home_assistant"); }
    QVariantList homeAssistantTiles() const { return homeAssistantTiles_; }
    QString homeAssistantStatus() const { return homeAssistantStatus_; }
    QString accentName() const { return settings_.value("appearance").toObject().value("accent").toString("orchid"); }
    QString appearanceStatus() const { return appearanceStatus_; }
    QString haUrl() const { return settings_.value("home_assistant").toObject().value("url").toString(); }
    QString haToken() const { return settings_.value("home_assistant").toObject().value("token").toString(); }
    QString haSettingsStatus() const { return haSettingsStatus_; }
    QVariantList haEntities() const { return haEntities_; }

    Q_INVOKABLE QString materialIcon(const QString &name) const {
        static const QHash<QString, QString> icons = {
            {"airplanemode_active", "\ue195"},
            {"arrow_back", "\ue5c4"},
            {"bluetooth", "\ue1a7"},
            {"brightness_medium", "\ue1ae"},
            {"camera_alt", "\ue3b0"},
            {"check_circle", "\ue86c"},
            {"chevron_right", "\ue5cc"},
            {"coffee", "\uefef"},
            {"content_paste", "\ue14f"},
            {"do_not_disturb_on", "\ue644"},
            {"home", "\ue88a"},
            {"hub", "\uee20"},
            {"invert_colors", "\ue891"},
            {"lightbulb", "\ue0f0"},
            {"lock", "\ue897"},
            {"nightlight", "\uf03d"},
            {"notifications", "\ue7f4"},
            {"pause", "\ue034"},
            {"person", "\ue7fd"},
            {"play_arrow", "\ue037"},
            {"power_settings_new", "\ue8ac"},
            {"public", "\ue80b"},
            {"settings", "\ue8b8"},
            {"show_chart", "\ue6e1"},
            {"skip_next", "\ue044"},
            {"skip_previous", "\ue045"},
            {"sports_esports", "\uea28"},
            {"storage", "\ue1db"},
            {"thermostat", "\ue1ff"},
            {"timer", "\ue425"},
            {"tune", "\ue429"},
            {"videocam", "\ue04b"},
            {"volume_up", "\ue050"},
            {"watch", "\ue334"},
            {"wifi", "\ue63e"},
        };
        return icons.value(name, "?");
    }

    Q_INVOKABLE void closeCenter() {
        QGuiApplication::quit();
    }

    Q_INVOKABLE void openSettingsApp(const QString &page) {
        const QString path = pyqtRoot_ + "/settings-page/settings.py";
        if (QFileInfo::exists(path)) {
            startDetachedCommand({pythonExecutable(), path, "--page", page});
        }
    }

    Q_INVOKABLE void openOverviewSettings() {
        openSettingsApp("overview");
    }

    Q_INVOKABLE void openLauncher() {
        const QString path = pyqtRoot_ + "/launcher/launcher.py";
        if (QFileInfo::exists(path)) {
            startDetachedCommand({pythonExecutable(), path});
        }
    }

    Q_INVOKABLE void toggleQuickSetting(const QString &key) {
        if (key == "wifi") {
            runScriptDetached(repoRoot_, "network.sh", {"toggle"});
        } else if (key == "bluetooth") {
            runScriptDetached(repoRoot_, "bluetooth", {"toggle"});
        } else if (key == "airplane") {
            runScriptDetached(repoRoot_, "network.sh", {"toggle-radio"});
        } else if (key == "night") {
            runScriptDetached(repoRoot_, "redshift", {"toggle"});
        } else if (key == "caffeine") {
            runScriptDetached(repoRoot_, "caffeine.sh", {"toggle"});
        } else if (key == "dnd") {
            const bool dndOn = runCommand(notificationControlCommand({"is-paused"})).trimmed() == "true";
            runCommand(notificationControlCommand({"set-paused", dndOn ? "false" : "true"}));
        }
        QTimer::singleShot(350, this, &NotificationCenterBackend::pollQuickSettings);
    }

    Q_INVOKABLE void setBrightness(int value) {
        pendingBrightness_ = std::clamp(value, 0, 100);
        if (brightness_ != pendingBrightness_) {
            brightness_ = pendingBrightness_;
            emit brightnessChanged();
        }
        brightnessCommitTimer_.start(90);
    }

    Q_INVOKABLE void setVolume(int value) {
        pendingVolume_ = std::clamp(value, 0, 100);
        if (volume_ != pendingVolume_) {
            volume_ = pendingVolume_;
            emit volumeChanged();
        }
        volumeCommitTimer_.start(90);
    }

    Q_INVOKABLE void triggerMediaAction(const QString &action) {
        QString translated = action;
        if (action == "toggle") {
            translated = "--toggle";
        } else if (action == "previous") {
            translated = "--previous";
        } else if (action == "next") {
            translated = "--next";
        }
        scriptOutput(repoRoot_, "mpris.sh", {translated}, 2500);
        QTimer::singleShot(150, this, &NotificationCenterBackend::pollMediaMetadata);
        QTimer::singleShot(450, this, &NotificationCenterBackend::pollMediaProgress);
    }

    Q_INVOKABLE void launchService(const QString &key) {
        if (!serviceEnabled(settings_, key)) {
            return;
        }
        if (key == "vpn_control") {
            launchPythonSingleton(pyqtRoot_ + "/widget-vpn-control/vpn_control.py");
        } else if (key == "christian_widget") {
            launchPythonSingleton(pyqtRoot_ + "/widget-religion-christian/christian_widget.py");
        } else if (key == "reminders_widget") {
            launchPythonSingleton(pyqtRoot_ + "/widget-reminders/reminders_widget.py");
        } else if (key == "pomodoro_widget") {
            launchPythonSingleton(pyqtRoot_ + "/widget-pomodoro/pomodoro_widget.py");
        } else if (key == "rss_widget") {
            launchPythonSingleton(pyqtRoot_ + "/widget-rss/rss_widget.py");
        } else if (key == "obs_widget") {
            launchPythonSingleton(pyqtRoot_ + "/widget-obs/obs_widget.py");
        } else if (key == "crypto_widget") {
            launchPythonSingleton(pyqtRoot_ + "/widget-crypto/crypto_widget.py");
        } else if (key == "vps_widget") {
            launchPythonSingleton(pyqtRoot_ + "/widget-vps/vps_widget.py");
        } else if (key == "desktop_clock_widget") {
            const QString nativeClock = binRoot_ + "/hanauta-clock";
            if (QFileInfo::exists(nativeClock)) {
                startDetachedCommand({nativeClock});
            } else {
                launchPythonSingleton(pyqtRoot_ + "/widget-desktop-clock/desktop_clock_widget.py");
            }
        } else if (key == "game_mode") {
            launchPythonSingleton(pyqtRoot_ + "/widget-game-mode/game_mode_popup.py");
        } else if (key == "home_assistant") {
            openSettingsApp("services");
        }
    }

    Q_INVOKABLE void setAccent(const QString &key) {
        QJsonObject appearance = settings_.value("appearance").toObject();
        appearance.insert("accent", key);
        settings_.insert("appearance", appearance);
        saveJsonObject(settingsFilePath(), settings_);
        appearanceStatus_ = QStringLiteral("Accent updated to %1.").arg(key);
        emit settingsChanged();
        rebuildServiceCards();
    }

    Q_INVOKABLE void setHomeAssistantUrl(const QString &url) {
        QJsonObject ha = settings_.value("home_assistant").toObject();
        ha.insert("url", url.trimmed().replace(QRegularExpression("/+$"), ""));
        settings_.insert("home_assistant", ha);
        emit settingsChanged();
    }

    Q_INVOKABLE void setHomeAssistantToken(const QString &token) {
        QJsonObject ha = settings_.value("home_assistant").toObject();
        ha.insert("token", token.trimmed());
        settings_.insert("home_assistant", ha);
        emit settingsChanged();
    }

    Q_INVOKABLE void saveHomeAssistantSettings() {
        saveJsonObject(settingsFilePath(), settings_);
        haSettingsStatus_ = QStringLiteral("Home Assistant settings saved.");
        emit settingsChanged();
        refreshHomeAssistant();
    }

    Q_INVOKABLE void refreshHomeAssistant() {
        if (!homeAssistantVisible()) {
            homeAssistantTiles_.clear();
            homeAssistantStatus_.clear();
            haEntities_.clear();
            emit homeAssistantChanged();
            emit settingsChanged();
            return;
        }
        const QString baseUrl = haUrl().trimmed();
        const QString token = haToken().trimmed();
        if (baseUrl.isEmpty() || token.isEmpty()) {
            homeAssistantStatus_ = QStringLiteral("Home Assistant URL and token are required.");
            rebuildHomeAssistantTiles();
            emit homeAssistantChanged();
            return;
        }
        QNetworkRequest request(QUrl(baseUrl + "/api/states"));
        request.setRawHeader("Authorization", QByteArray("Bearer ") + token.toUtf8());
        request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
        QNetworkReply *reply = network_.get(request);
        reply->setProperty("hanauta_request", "ha_states");
    }

    Q_INVOKABLE void togglePinEntity(const QString &entityId) {
        QJsonObject ha = settings_.value("home_assistant").toObject();
        QJsonArray pinned = ha.value("pinned_entities").toArray();
        QJsonArray next;
        bool removed = false;
        for (const QJsonValue &value : pinned) {
            if (value.toString() == entityId) {
                removed = true;
                continue;
            }
            next.append(value);
        }
        if (!removed) {
            if (next.size() >= 5) {
                haSettingsStatus_ = QStringLiteral("You can pin up to five entities.");
                emit settingsChanged();
                return;
            }
            next.append(entityId);
        }
        ha.insert("pinned_entities", next);
        settings_.insert("home_assistant", ha);
        saveJsonObject(settingsFilePath(), settings_);
        haSettingsStatus_ = QStringLiteral("%1/5 entities pinned.").arg(next.size());
        emit settingsChanged();
        rebuildHomeAssistantTiles();
        rebuildHomeAssistantEntities();
    }

    Q_INVOKABLE void activateHomeAssistantTile(int index) {
        const QJsonArray pinned = settings_.value("home_assistant").toObject().value("pinned_entities").toArray();
        if (index < 0 || index >= pinned.size()) {
            return;
        }
        const QString entityId = pinned.at(index).toString();
        const QJsonObject entity = haEntityMap_.value(entityId);
        if (entity.isEmpty()) {
            homeAssistantStatus_ = QStringLiteral("Entity state is not loaded yet.");
            emit homeAssistantChanged();
            return;
        }
        QString domain = entityId.section('.', 0, 0);
        QString serviceDomain = domain;
        QString service;
        const QString state = entity.value("state").toString();
        QJsonObject payload{{"entity_id", entityId}};
        if (domain == "light" || domain == "switch" || domain == "input_boolean") {
            service = state == "on" ? "turn_off" : "turn_on";
        } else if (domain == "scene" || domain == "script") {
            service = "turn_on";
        } else {
            homeAssistantStatus_ = entityId + " is view-only right now.";
            emit homeAssistantChanged();
            return;
        }
        QNetworkRequest request(QUrl(haUrl().trimmed() + "/api/services/" + serviceDomain + "/" + service));
        request.setRawHeader("Authorization", QByteArray("Bearer ") + haToken().trimmed().toUtf8());
        request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
        QNetworkReply *reply = network_.post(request, QJsonDocument(payload).toJson(QJsonDocument::Compact));
        reply->setProperty("hanauta_request", "ha_toggle");
        reply->setProperty("entity_id", entityId);
        reply->setProperty("service_name", service);
    }

    Q_INVOKABLE void refreshAll() {
        updateHeader();
        pollQuickSettings();
        pollSliders();
        pollMediaMetadata();
        pollMediaProgress();
        pollPhone();
        rebuildSystemOverview();
        reloadSettings();
        rebuildServiceCards();
        refreshHomeAssistant();
    }

signals:
    void usernameChanged();
    void uptimeChanged();
    void paletteChanged();
    void quickSettingsChanged();
    void brightnessChanged();
    void volumeChanged();
    void mediaChanged();
    void phoneInfoChanged();
    void serviceCardsChanged();
    void systemOverviewChanged();
    void homeAssistantChanged();
    void settingsChanged();

private slots:
    void commitBrightness() {
        runScriptDetached(repoRoot_, "brightness.sh", {"set", QString::number(pendingBrightness_)});
    }

    void commitVolume() {
        runScriptDetached(repoRoot_, "volume.sh", {"set", QString::number(pendingVolume_)});
    }

    void onNetworkReplyFinished(QNetworkReply *reply) {
        const QString kind = reply->property("hanauta_request").toString();
        const int statusCode = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        const QByteArray body = reply->readAll();
        reply->deleteLater();

        if (kind == "ha_states") {
            if (reply->error() != QNetworkReply::NoError || statusCode >= 400) {
                homeAssistantStatus_ = statusCode > 0
                    ? QStringLiteral("Home Assistant returned HTTP %1.").arg(statusCode)
                    : QStringLiteral("Unable to reach Home Assistant.");
                haSettingsStatus_ = homeAssistantStatus_;
                haEntities_.clear();
                haEntityMap_.clear();
                rebuildHomeAssistantTiles();
                emit homeAssistantChanged();
                emit settingsChanged();
                return;
            }
            const QJsonDocument doc = QJsonDocument::fromJson(body);
            if (!doc.isArray()) {
                homeAssistantStatus_ = QStringLiteral("No entities available.");
                haSettingsStatus_ = homeAssistantStatus_;
                haEntities_.clear();
                haEntityMap_.clear();
                rebuildHomeAssistantTiles();
                emit homeAssistantChanged();
                emit settingsChanged();
                return;
            }
            QList<QJsonObject> entities;
            haEntityMap_.clear();
            for (const QJsonValue &value : doc.array()) {
                if (!value.isObject()) {
                    continue;
                }
                const QJsonObject object = value.toObject();
                const QString entityId = object.value("entity_id").toString();
                if (entityId.isEmpty()) {
                    continue;
                }
                entities.append(object);
                haEntityMap_.insert(entityId, object);
            }
            std::sort(entities.begin(), entities.end(), [](const QJsonObject &left, const QJsonObject &right) {
                return left.value("entity_id").toString() < right.value("entity_id").toString();
            });
            haEntities_.clear();
            int count = 0;
            for (const QJsonObject &entity : entities) {
                if (count >= 80) {
                    break;
                }
                const QString entityId = entity.value("entity_id").toString();
                const QString state = entity.value("state").toString("unknown");
                const QJsonObject attrs = entity.value("attributes").toObject();
                const QString name = attrs.value("friendly_name").toString(entityId);
                const bool pinned = settings_.value("home_assistant").toObject().value("pinned_entities").toArray().contains(entityId);
                haEntities_.append(QVariantMap{
                    {"entity_id", entityId},
                    {"name", name},
                    {"state", state},
                    {"pinned", pinned},
                });
                count += 1;
            }
            homeAssistantStatus_ = QStringLiteral("Pinned entity controls are live.");
            haSettingsStatus_ = QStringLiteral("Entities loaded successfully.");
            rebuildHomeAssistantTiles();
            emit homeAssistantChanged();
            emit settingsChanged();
            return;
        }

        if (kind == "ha_toggle") {
            const QString entityId = reply->property("entity_id").toString();
            const QString service = reply->property("service_name").toString();
            homeAssistantStatus_ = reply->error() == QNetworkReply::NoError && statusCode < 400
                ? QStringLiteral("Triggered %1 for %2.").arg(service, entityId)
                : (statusCode > 0
                    ? QStringLiteral("Home Assistant returned HTTP %1.").arg(statusCode)
                    : QStringLiteral("Unable to reach Home Assistant."));
            emit homeAssistantChanged();
            QTimer::singleShot(900, this, &NotificationCenterBackend::refreshHomeAssistant);
        }
    }

private:
    QString pythonExecutable() const {
        const QString venv = repoRoot_ + "/../.venv/bin/python";
        if (QFileInfo::exists(venv)) {
            return venv;
        }
        return QStringLiteral("python3");
    }

    QStringList notificationControlCommand(const QStringList &args = {}) const {
        const QString local = binRoot_ + "/hanauta-notifyctl";
        QStringList command{QFileInfo::exists(local) ? local : QStringLiteral("hanauta-notifyctl")};
        command.append(args);
        return command;
    }

    void launchPythonSingleton(const QString &scriptPath) {
        if (!QFileInfo::exists(scriptPath)) {
            return;
        }
        terminateBackgroundMatches(scriptPath);
        startDetachedCommand({pythonExecutable(), scriptPath});
    }

    void reloadSettings() {
        settings_ = mergedSettings();
        saveJsonObject(settingsFilePath(), settings_);
        settingsMtime_ = QFileInfo(settingsFilePath()).lastModified().toMSecsSinceEpoch();
        emit settingsChanged();
    }

    void reloadTheme() {
        themeMtime_ = QFileInfo(paletteFilePath()).lastModified().toMSecsSinceEpoch();
        const ThemePalette theme = loadThemePalette();
        const QJsonObject appearance = settings_.value("appearance").toObject();
        const bool transparencyEnabled = appearance.value("transparency").toBool(true);
        const double panelOpacity = transparencyEnabled
            ? appearance.value("notification_center_panel_opacity").toInt(84) / 100.0
            : 1.0;
        const double cardOpacity = transparencyEnabled
            ? appearance.value("notification_center_card_opacity").toInt(92) / 100.0
            : 1.0;
        palette_ = {
            {"primary", theme.primary},
            {"onPrimary", theme.onPrimary},
            {"primaryContainer", theme.primaryContainer},
            {"secondary", theme.secondary},
            {"tertiary", theme.tertiary},
            {"surfaceContainer", theme.surfaceContainer},
            {"surfaceContainerHigh", theme.surfaceContainerHigh},
            {"onSurface", theme.onSurface},
            {"onSurfaceVariant", theme.onSurfaceVariant},
            {"outline", theme.outline},
            {"error", theme.error},
            {"onError", theme.onError},
            {"panelBg", rgba(theme.surfaceContainer, panelOpacity)},
            {"panelBorder", rgba(theme.outline, 0.20)},
            {"cardBg", rgba(theme.surfaceContainerHigh, std::max(0.35, cardOpacity - 0.06))},
            {"cardStrongBg", rgba(theme.surfaceContainerHigh, cardOpacity)},
            {"hoverBg", rgba(theme.primary, 0.14)},
            {"accentSoft", rgba(theme.primary, 0.18)},
            {"text", theme.onSurface},
            {"textMuted", rgba(theme.onSurfaceVariant, 0.78)},
            {"inactive", rgba(theme.onSurfaceVariant, 0.68)},
            {"icon", theme.onSurface},
            {"mediaStart", rgba(theme.primaryContainer, std::max(cardOpacity, 0.84))},
            {"mediaEnd", rgba(blend(theme.primary, theme.secondary, 0.38), std::max(cardOpacity, 0.84))},
            {"mediaBorder", rgba(theme.primary, 0.72)},
            {"playFg", theme.onPrimary},
            {"dangerBg", theme.error},
            {"dangerFg", theme.onError},
            {"phoneOnline", theme.primary},
            {"phoneOffline", rgba(theme.onSurfaceVariant, 0.18)},
        };
        emit paletteChanged();
    }

    void reloadIfChanged() {
        const qint64 currentThemeMtime = QFileInfo(paletteFilePath()).lastModified().toMSecsSinceEpoch();
        if (currentThemeMtime != themeMtime_) {
            reloadTheme();
        }
        const qint64 currentSettingsMtime = QFileInfo(settingsFilePath()).lastModified().toMSecsSinceEpoch();
        if (currentSettingsMtime != settingsMtime_) {
            settingsMtime_ = currentSettingsMtime;
            reloadSettings();
            reloadTheme();
            rebuildServiceCards();
            rebuildSystemOverview();
            refreshHomeAssistant();
        }
    }

    void updateHeader() {
        const QString nextUser = currentUsername();
        const QString nextUptime = formatUptime(readUptimeSeconds());
        if (nextUser != username_) {
            username_ = nextUser;
            emit usernameChanged();
        }
        if (nextUptime != uptime_) {
            uptime_ = nextUptime;
            emit uptimeChanged();
        }
    }

    void rebuildSystemOverview() {
        systemOverview_ = {
            QVariantMap{{"label", "Host"}, {"value", runCommand({"hostname"}).trimmed().isEmpty() ? QStringLiteral("Unknown") : runCommand({"hostname"})}},
            QVariantMap{{"label", "Kernel"}, {"value", runCommand({"uname", "-r"}).trimmed().isEmpty() ? QStringLiteral("Unknown") : runCommand({"uname", "-r"})}},
            QVariantMap{{"label", "Session"}, {"value", QString::fromUtf8(qgetenv("XDG_SESSION_DESKTOP")).isEmpty() ? QStringLiteral("i3") : QString::fromUtf8(qgetenv("XDG_SESSION_DESKTOP"))}},
            QVariantMap{{"label", "Toolkit"}, {"value", QStringLiteral("Qt/QML native")}},
            QVariantMap{{"label", "Uptime"}, {"value", QStringLiteral("up %1").arg(uptime_)}},
            QVariantMap{{"label", "Theme"}, {"value", loadThemePalette().useMatugen ? QStringLiteral("Matugen") : QStringLiteral("Fallback")}},
        };
        emit systemOverviewChanged();
    }

    void pollQuickSettings() {
        const bool wifiOn = scriptOutput(repoRoot_, "network.sh", {"status"}) == "Connected";
        const QString wifiName = scriptOutput(repoRoot_, "network.sh", {"ssid"});
        const bool bluetoothOn = scriptOutput(repoRoot_, "bluetooth", {"state"}) == "on";
        const bool dndOn = runCommand(notificationControlCommand({"is-paused"})).trimmed() == "true";
        const bool airplaneOn = scriptOutput(repoRoot_, "network.sh", {"radio-status"}) == "off";
        const bool nightOn = scriptOutput(repoRoot_, "redshift", {"state"}) == "on";
        const bool caffeineOn = scriptOutput(repoRoot_, "caffeine.sh", {"status"}) == "on";

        quickSettings_ = {
            quickItem("wifi", "Wi-Fi", "wifi", wifiOn, wifiName.isEmpty() ? QStringLiteral("Disconnected") : wifiName),
            quickItem("bluetooth", "Bluetooth", "bluetooth", bluetoothOn, bluetoothOn ? QStringLiteral("Connected") : QStringLiteral("Off")),
            quickItem("dnd", "DND", "do_not_disturb_on", dndOn, dndOn ? QStringLiteral("On") : QStringLiteral("Off")),
            quickItem("airplane", "Airplane", "airplanemode_active", airplaneOn, airplaneOn ? QStringLiteral("On") : QStringLiteral("Off")),
            quickItem("night", "Night Light", "nightlight", nightOn, nightOn ? QStringLiteral("On") : QStringLiteral("Off")),
            quickItem("caffeine", "Caffeine", "coffee", caffeineOn, caffeineOn ? QStringLiteral("On") : QStringLiteral("Off")),
        };
        emit quickSettingsChanged();
    }

    QVariantMap quickItem(const QString &key, const QString &title, const QString &icon, bool active, const QString &subtitle) const {
        return {
            {"key", key},
            {"title", title},
            {"icon", icon},
            {"active", active},
            {"subtitle", subtitle},
        };
    }

    void pollSliders() {
        bool ok = false;
        const int nextBrightness = scriptOutput(repoRoot_, "brightness.sh", {"br"}).toInt(&ok);
        const int safeBrightness = ok ? std::clamp(nextBrightness, 0, 100) : 67;
        if (safeBrightness != brightness_) {
            brightness_ = safeBrightness;
            emit brightnessChanged();
        }
        ok = false;
        const int nextVolume = scriptOutput(repoRoot_, "volume.sh", {"vol"}).toInt(&ok);
        const int safeVolume = ok ? std::clamp(nextVolume, 0, 100) : 82;
        if (safeVolume != volume_) {
            volume_ = safeVolume;
            emit volumeChanged();
        }
    }

    void pollMediaMetadata() {
        const QString title = scriptOutput(repoRoot_, "mpris.sh", {"title"});
        const QString artist = scriptOutput(repoRoot_, "mpris.sh", {"artist"});
        const QString status = scriptOutput(repoRoot_, "mpris.sh", {"status"});
        const QString player = scriptOutput(repoRoot_, "mpris.sh", {"player"});
        const QString art = scriptOutput(repoRoot_, "mpris.sh", {"coverloc"});
        mediaPlayer_ = player;
        mediaStatus_ = status.isEmpty() ? QStringLiteral("Stopped") : status;
        mediaTitle_ = title.isEmpty() ? QStringLiteral("No music") : title;
        mediaArtist_ = artist.isEmpty() ? QStringLiteral("No artist") : artist;
        if (!art.isEmpty() && QFileInfo::exists(art)) {
            mediaCover_ = QUrl::fromLocalFile(art).toString();
        } else {
            mediaCover_.clear();
        }
        emit mediaChanged();
    }

    void pollMediaProgress() {
        const QString player = mediaPlayer_.isEmpty() ? scriptOutput(repoRoot_, "mpris.sh", {"player"}) : mediaPlayer_;
        if (player.isEmpty()) {
            mediaProgress_ = 0.0;
            mediaElapsed_ = "0:00";
            mediaTotal_ = "0:00";
            emit mediaChanged();
            return;
        }
        const QString status = runCommand({"playerctl", "--player=" + player, "status"});
        const QString positionRaw = runCommand({"playerctl", "--player=" + player, "position"});
        const QString lengthRaw = runCommand({"playerctl", "--player=" + player, "metadata", "--format", "{{mpris:length}}"});
        bool ok = false;
        const int positionMs = static_cast<int>(positionRaw.toDouble(&ok) * 1000.0);
        const int safePosition = ok ? std::max(0, positionMs) : 0;
        ok = false;
        const int durationMs = lengthRaw.toInt(&ok) / 1000;
        const int safeDuration = ok ? std::max(0, durationMs) : 0;
        mediaStatus_ = status.isEmpty() ? mediaStatus_ : status;
        mediaElapsed_ = formatMillis(safePosition);
        mediaTotal_ = formatMillis(safeDuration);
        mediaProgress_ = safeDuration > 0 ? std::clamp(static_cast<double>(safePosition) / safeDuration, 0.0, 1.0) : 0.0;
        emit mediaChanged();
    }

    void pollPhone() {
        const QString raw = scriptOutput(repoRoot_, "phone_info.sh");
        const QJsonDocument doc = QJsonDocument::fromJson(raw.toUtf8());
        const QJsonObject obj = doc.isObject() ? doc.object() : QJsonObject();
        const QString name = obj.value("name").toString();
        const QString status = obj.value("status").toString("Offline");
        const QString battery = obj.value("battery").toVariant().toString();
        const bool hasDevice = !obj.value("id").toString().isEmpty() && name != "Disconnected";
        phoneInfo_ = {
            {"name", hasDevice ? name : QStringLiteral("No devices connected")},
            {"status", hasDevice ? status : QString()},
            {"battery", hasDevice ? battery + "%" : QString()},
            {"clipboardActive", obj.value("clipboard").toString() == "on"},
            {"online", hasDevice && status.toLower() != "offline"},
        };
        emit phoneInfoChanged();
    }

    void rebuildServiceCards() {
        const QList<QVariantMap> candidates = {
            serviceCard("home_assistant", "Home Assistant", "Open service settings and pinned entity controls.", "hub"),
            serviceCard("vpn_control", "VPN Control", "Open the WireGuard popup from the notification center.", "lock"),
            serviceCard("christian_widget", "Christian Widget", "Open the devotion widget from the notification center.", "check_circle"),
            serviceCard("reminders_widget", "Reminders", "Open tracked CalDAV reminders and tea reminders.", "notifications"),
            serviceCard("pomodoro_widget", "Pomodoro", "Open the focus timer with work and break modes.", "timer"),
            serviceCard("rss_widget", "RSS", "Open the styled RSS reader for manual feeds or OPML sources.", "public"),
            serviceCard("obs_widget", "OBS", "Open livestreaming and recording controls for OBS WebSocket.", "videocam"),
            serviceCard("crypto_widget", "Crypto Tracker", "Open tracked coins, charts, and price alerts.", "show_chart"),
            serviceCard("vps_widget", "VPS Care", "Open SSH-powered VPS health checks and quick actions.", "storage"),
            serviceCard("desktop_clock_widget", "Desktop Clock", "Open the Hanauta analog desktop clock.", "watch"),
            serviceCard("game_mode", "Game Mode", "Open the Game Mode popup and control gamemoded.", "sports_esports"),
        };
        serviceCards_.clear();
        for (const QVariantMap &card : candidates) {
            if (card.value("visible").toBool()) {
                serviceCards_.append(card);
            }
        }
        emit serviceCardsChanged();
    }

    QVariantMap serviceCard(const QString &key, const QString &title, const QString &detail, const QString &icon) const {
        return {
            {"key", key},
            {"title", title},
            {"detail", detail},
            {"icon", icon},
            {"visible", serviceVisible(settings_, key)},
        };
    }

    void rebuildHomeAssistantTiles() {
        homeAssistantTiles_.clear();
        const QJsonArray pinned = settings_.value("home_assistant").toObject().value("pinned_entities").toArray();
        for (int index = 0; index < 5; ++index) {
            if (index >= pinned.size()) {
                homeAssistantTiles_.append(QVariantMap{
                    {"icon", "hub"},
                    {"title", QStringLiteral("Slot %1").arg(index + 1)},
                    {"subtitle", QStringLiteral("Empty")},
                    {"enabled", false},
                });
                continue;
            }
            const QString entityId = pinned.at(index).toString();
            const QJsonObject entity = haEntityMap_.value(entityId);
            const QJsonObject attrs = entity.value("attributes").toObject();
            const QString name = attrs.value("friendly_name").toString(entityId);
            const QString state = entity.value("state").toString("Unavailable");
            const QString domain = entityId.section('.', 0, 0);
            const QString icon = domain == "light" ? "lightbulb"
                : domain == "switch" ? "tune"
                : domain == "climate" ? "thermostat"
                : domain == "camera" ? "camera_alt"
                : "home";
            homeAssistantTiles_.append(QVariantMap{
                {"icon", icon},
                {"title", name.left(12)},
                {"subtitle", state.left(12)},
                {"enabled", true},
            });
        }
        emit homeAssistantChanged();
    }

    void rebuildHomeAssistantEntities() {
        for (int index = 0; index < haEntities_.size(); ++index) {
            QVariantMap item = haEntities_.at(index).toMap();
            item["pinned"] = settings_.value("home_assistant").toObject().value("pinned_entities").toArray().contains(item.value("entity_id").toString());
            haEntities_[index] = item;
        }
        emit settingsChanged();
    }

    QString repoRoot_;
    QString pyqtRoot_;
    QString binRoot_;
    QNetworkAccessManager network_;
    QTimer pollTimer_;
    QTimer themeTimer_;
    QTimer mediaTimer_;
    QTimer uptimeTimer_;
    QTimer brightnessCommitTimer_;
    QTimer volumeCommitTimer_;
    qint64 themeMtime_ = -1;
    qint64 settingsMtime_ = -1;

    QString username_ = currentUsername();
    QString uptime_ = formatUptime(readUptimeSeconds());
    QJsonObject settings_;
    QVariantMap palette_;
    QVariantList quickSettings_;
    int brightness_ = 67;
    int volume_ = 82;
    int pendingBrightness_ = 67;
    int pendingVolume_ = 82;
    QString mediaTitle_ = "No music";
    QString mediaArtist_ = "No artist";
    QString mediaStatus_ = "Stopped";
    QString mediaCover_;
    QString mediaPlayer_;
    double mediaProgress_ = 0.0;
    QString mediaElapsed_ = "0:00";
    QString mediaTotal_ = "0:00";
    QVariantMap phoneInfo_;
    QVariantList serviceCards_;
    QVariantList systemOverview_;
    QVariantList homeAssistantTiles_;
    QString homeAssistantStatus_;
    QString appearanceStatus_;
    QString haSettingsStatus_ = "Pin up to five entities.";
    QVariantList haEntities_;
    QHash<QString, QJsonObject> haEntityMap_;
};

int main(int argc, char *argv[]) {
    QGuiApplication app(argc, argv);
    app.setApplicationName("Hanauta Control Center");
    app.setDesktopFileName("HanautaControlCenter");

    const QString appDir = QCoreApplication::applicationDirPath();
    const QString repoRoot = QDir(appDir + "/..").absolutePath();
    loadAppFonts(repoRoot);

    const QString qmlPath = repoRoot + "/src/pyqt/notification-center/notification_center.qml";
    if (!QFile::exists(qmlPath)) {
        fprintf(stderr, "ERROR: QML file not found: %s\n", qPrintable(qmlPath));
        return 2;
    }

    QQmlApplicationEngine engine;
    NotificationCenterBackend backend(repoRoot);
    engine.rootContext()->setContextProperty("backend", &backend);
    engine.load(QUrl::fromLocalFile(qmlPath));
    if (engine.rootObjects().isEmpty()) {
        fprintf(stderr, "ERROR: failed to load QML (no root objects).\n");
        return 3;
    }

    return app.exec();
}

#include "hanauta-control-center.moc"
