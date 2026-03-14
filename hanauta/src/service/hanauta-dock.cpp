#include <QCoreApplication>
#include <QCursor>
#include <QDateTime>
#include <QDir>
#include <QDirIterator>
#include <QFile>
#include <QFontDatabase>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMap>
#include <QPointer>
#include <QProcess>
#include <QQuickStyle>
#include <QQuickWindow>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QRegularExpression>
#include <QScreen>
#include <QStandardPaths>
#include <QStringList>
#include <QTimer>
#include <QUrl>
#include <QtQml>

#include <algorithm>
#include <cstdio>

#if __has_include(<X11/Xatom.h>) && __has_include(<X11/Xlib.h>)
#include <X11/Xatom.h>
#include <X11/Xlib.h>
#ifdef Bool
#undef Bool
#endif
#define HANAUTA_HAS_X11 1
#else
#define HANAUTA_HAS_X11 0
#endif

namespace {

QString repoRoot() {
    return QDir(QCoreApplication::applicationDirPath() + "/..").absolutePath();
}

QString paletteFilePath() {
    return QDir::homePath() + "/.local/state/hanauta/theme/pyqt_palette.json";
}

QString dockConfigPath() {
    return repoRoot() + "/src/pyqt/dock/dock.toml";
}

QString launcherScriptPath() {
    return repoRoot() + "/src/pyqt/launcher/launcher.py";
}

QString volumeScriptPath() {
    return repoRoot() + "/src/eww/scripts/volume.sh";
}

QString cacheDirPath() {
    const QString base = qEnvironmentVariable("XDG_CACHE_HOME", QDir::homePath() + "/.cache");
    return base + "/hanauta-dock";
}

QString stateFilePath() {
    return cacheDirPath() + "/state.json";
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

QJsonObject runJsonCommand(const QStringList &command) {
    if (command.isEmpty()) {
        return {};
    }
    QProcess process;
    process.start(command.first(), command.mid(1));
    if (!process.waitForFinished(3000)) {
        return {};
    }
    const QJsonDocument doc = QJsonDocument::fromJson(process.readAllStandardOutput());
    return doc.isObject() ? doc.object() : QJsonObject();
}

QJsonArray runJsonArrayCommand(const QStringList &command) {
    if (command.isEmpty()) {
        return {};
    }
    QProcess process;
    process.start(command.first(), command.mid(1));
    if (!process.waitForFinished(3000)) {
        return {};
    }
    const QJsonDocument doc = QJsonDocument::fromJson(process.readAllStandardOutput());
    return doc.isArray() ? doc.array() : QJsonArray();
}

QString runCommandText(const QStringList &command, int timeoutMs = 3000) {
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

bool runDetachedCommand(const QStringList &command) {
    if (command.isEmpty()) {
        return false;
    }
    const QString program = QStandardPaths::findExecutable(command.first());
    if (program.isEmpty()) {
        return false;
    }
    return QProcess::startDetached(program, command.mid(1));
}

bool commandExists(const QString &command) {
    return !QStandardPaths::findExecutable(command).isEmpty();
}

QString pythonBinaryPath() {
    const QString venv = QDir(repoRoot()).absoluteFilePath("../.venv/bin/python");
    if (QFile::exists(venv)) {
        return venv;
    }
    const QString python3 = QStandardPaths::findExecutable("python3");
    return python3.isEmpty() ? QStringLiteral("python") : python3;
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
        {"apps", QString::fromUtf8("\uE5C3")},
        {"settings", QString::fromUtf8("\uE8B8")},
        {"volume_down", QString::fromUtf8("\uE04D")},
        {"volume_mute", QString::fromUtf8("\uE04E")},
        {"volume_off", QString::fromUtf8("\uE04F")},
        {"volume_up", QString::fromUtf8("\uE050")},
        {"open_in_new", QString::fromUtf8("\uE89E")},
        {"arrow_back", QString::fromUtf8("\uE5C4")},
    };
    return icons.value(name, "?");
}

struct ThemePalette {
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
    palette.secondary = normalizeHex(obj.value("secondary").toString(palette.secondary), palette.secondary);
    palette.tertiary = normalizeHex(obj.value("tertiary").toString(palette.tertiary), palette.tertiary);
    palette.surfaceContainer = normalizeHex(obj.value("surface_container").toString(palette.surfaceContainer), palette.surfaceContainer);
    palette.surfaceContainerHigh = normalizeHex(obj.value("surface_container_high").toString(palette.surfaceContainerHigh), palette.surfaceContainerHigh);
    palette.onSurface = normalizeHex(obj.value("on_surface").toString(palette.onSurface), palette.onSurface);
    palette.onSurfaceVariant = normalizeHex(obj.value("on_surface_variant").toString(palette.onSurfaceVariant), palette.onSurfaceVariant);
    palette.outline = normalizeHex(obj.value("outline").toString(palette.outline), palette.outline);
    return palette;
}

struct DockConfig {
    bool autoHide = false;
    int width = 60;
    QString widthUnit = "%";
    int height = 64;
    bool iconsLeft = false;
    QString position = "center";
    int transparency = 60;
    QStringList pinnedApps;
    QStringList blacklistWm;
    QStringList blacklistDesktop;
    QStringList blacklistWindowName;
};

QStringList parseTomlArray(const QStringList &lines, int *index) {
    QStringList values;
    QString current = lines.value(*index).section('=', 1).trimmed();
    if (!current.startsWith('[')) {
        return values;
    }
    QString block = current;
    while (!block.contains(']') && *index + 1 < lines.size()) {
        *index += 1;
        block += lines.value(*index).trimmed();
    }
    block.remove('[');
    block.remove(']');
    const QRegularExpression regex("\"([^\"]+)\"");
    QRegularExpressionMatchIterator it = regex.globalMatch(block);
    while (it.hasNext()) {
        values.append(it.next().captured(1));
    }
    return values;
}

DockConfig loadDockConfig() {
    DockConfig config;
    QFile file(dockConfigPath());
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        return config;
    }
    QString section;
    const QStringList lines = QString::fromUtf8(file.readAll()).split('\n');
    for (int i = 0; i < lines.size(); ++i) {
        QString line = lines.at(i).trimmed();
        if (line.isEmpty() || line.startsWith('#')) {
            continue;
        }
        if (line.startsWith('[') && line.endsWith(']')) {
            section = line.mid(1, line.size() - 2).trimmed();
            continue;
        }
        if (!line.contains('=')) {
            continue;
        }
        const QString key = line.section('=', 0, 0).trimmed();
        const QString value = line.section('=', 1).trimmed();
        if (section == "dock") {
            if (key == "auto_hide") config.autoHide = value == "true";
            else if (key == "width") config.width = value.toInt();
            else if (key == "width_unit") config.widthUnit = value.mid(1, value.size() - 2);
            else if (key == "height") config.height = value.toInt();
            else if (key == "icons_left") config.iconsLeft = value == "true";
            else if (key == "position") config.position = value.mid(1, value.size() - 2);
            else if (key == "transparency") config.transparency = value.toInt();
        } else if (section == "pinned" && key == "apps") {
            config.pinnedApps = parseTomlArray(lines, &i);
        } else if (section == "blacklist" && key == "wm_class") {
            config.blacklistWm = parseTomlArray(lines, &i);
        } else if (section == "blacklist" && key == "desktop_id") {
            config.blacklistDesktop = parseTomlArray(lines, &i);
        } else if (section == "blacklist" && key == "window_name") {
            config.blacklistWindowName = parseTomlArray(lines, &i);
        }
    }
    return config;
}

QString formatTomlList(const QStringList &values) {
    if (values.isEmpty()) {
        return "[]";
    }
    QStringList rows;
    for (const QString &value : values) {
        rows.append(QStringLiteral("  \"%1\"").arg(value));
    }
    return QStringLiteral("[\n%1\n]").arg(rows.join(",\n"));
}

void saveDockConfig(const DockConfig &config) {
    QFile file(dockConfigPath());
    if (!file.open(QIODevice::WriteOnly | QIODevice::Text)) {
        return;
    }
    const QString body =
        "[dock]\n"
        + QStringLiteral("auto_hide = %1\n").arg(config.autoHide ? "true" : "false")
        + QStringLiteral("width = %1\n").arg(config.width)
        + QStringLiteral("width_unit = \"%1\"\n").arg(config.widthUnit)
        + QStringLiteral("height = %1\n").arg(config.height)
        + QStringLiteral("icons_left = %1\n\n").arg(config.iconsLeft ? "true" : "false")
        + QStringLiteral("position = \"%1\"\n\n").arg(config.position)
        + QStringLiteral("transparency = %1\n\n").arg(config.transparency)
        + "[pinned]\n"
        + QStringLiteral("apps = %1\n\n").arg(formatTomlList(config.pinnedApps))
        + "[blacklist]\n"
        + QStringLiteral("wm_class = %1\n\n").arg(formatTomlList(config.blacklistWm))
        + QStringLiteral("desktop_id = %1\n\n").arg(formatTomlList(config.blacklistDesktop))
        + QStringLiteral("window_name = %1\n").arg(formatTomlList(config.blacklistWindowName));
    file.write(body.toUtf8());
}

QString normalize(const QString &value) {
    return value.trimmed().toLower();
}

bool globMatch(const QString &value, const QStringList &patterns) {
    const QString normalized = normalize(value);
    for (const QString &pattern : patterns) {
        QRegularExpression regex(
            QRegularExpression::wildcardToRegularExpression(normalize(pattern)),
            QRegularExpression::CaseInsensitiveOption
        );
        if (regex.match(normalized).hasMatch()) {
            return true;
        }
    }
    return false;
}

struct DesktopEntry {
    QString desktopId;
    QString name;
    QString icon;
    QString startupWmClass;
};

struct WindowEntry {
    int conId = 0;
    QString wmClass;
    QString title;
    bool focused = false;
    QString workspace;
};

void walkTreeNode(const QJsonObject &node, const QString &workspaceName, QList<WindowEntry> *windows) {
    QString currentWorkspace = workspaceName;
    if (node.value("type").toString() == "workspace") {
        currentWorkspace = node.value("name").toString();
    }
    if (!node.value("window").isNull()) {
        const QJsonObject properties = node.value("window_properties").toObject();
        const QString wmClass = normalize(properties.value("class").toString(properties.value("instance").toString()));
        const int conId = node.value("id").toInt();
        if (!wmClass.isEmpty() && conId > 0) {
            WindowEntry entry;
            entry.conId = conId;
            entry.wmClass = wmClass;
            entry.title = node.value("name").toString(properties.value("title").toString()).trimmed();
            entry.focused = node.value("focused").toBool(false);
            entry.workspace = currentWorkspace;
            windows->append(entry);
        }
    }
    const QJsonArray nodes = node.value("nodes").toArray();
    for (const QJsonValue &child : nodes) {
        walkTreeNode(child.toObject(), currentWorkspace, windows);
    }
    const QJsonArray floating = node.value("floating_nodes").toArray();
    for (const QJsonValue &child : floating) {
        walkTreeNode(child.toObject(), currentWorkspace, windows);
    }
}

QList<WindowEntry> getOpenWindows() {
    QList<WindowEntry> windows;
    walkTreeNode(runJsonCommand({"i3-msg", "-t", "get_tree"}), QString(), &windows);
    return windows;
}

QString currentWorkspace() {
    const QJsonArray workspaces = runJsonArrayCommand({"i3-msg", "-t", "get_workspaces"});
    for (const QJsonValue &value : workspaces) {
        const QJsonObject obj = value.toObject();
        if (obj.value("focused").toBool(false)) {
            return obj.value("name").toString();
        }
    }
    return {};
}

int focusedConId() {
    const QList<WindowEntry> windows = getOpenWindows();
    for (const WindowEntry &entry : windows) {
        if (entry.focused) {
            return entry.conId;
        }
    }
    return 0;
}

QPair<QMap<QString, DesktopEntry>, QMap<QString, QString>> scanDesktopEntries() {
    const QStringList desktopDirs = {
        QDir::homePath() + "/.local/share/applications",
        "/usr/local/share/applications",
        "/usr/share/applications",
    };
    QMap<QString, DesktopEntry> entries;
    QMap<QString, QString> wmToDesktop;
    for (const QString &dirPath : desktopDirs) {
        QDir dir(dirPath);
        if (!dir.exists()) {
            continue;
        }
        const QFileInfoList files = dir.entryInfoList({"*.desktop"}, QDir::Files | QDir::Readable);
        for (const QFileInfo &info : files) {
            QFile file(info.filePath());
            if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
                continue;
            }
            QString name;
            QString icon;
            QString startupWmClass;
            bool inDesktopEntry = false;
            const QStringList lines = QString::fromUtf8(file.readAll()).split('\n');
            for (const QString &rawLine : lines) {
                const QString line = rawLine.trimmed();
                if (line == "[Desktop Entry]") {
                    inDesktopEntry = true;
                    continue;
                }
                if (line.startsWith('[') && line.endsWith(']') && line != "[Desktop Entry]") {
                    inDesktopEntry = false;
                    continue;
                }
                if (!inDesktopEntry || !line.contains('=')) {
                    continue;
                }
                const QString key = line.section('=', 0, 0).trimmed();
                const QString value = line.section('=', 1).trimmed();
                if (key == "Name" && name.isEmpty()) name = value;
                else if (key == "Icon" && icon.isEmpty()) icon = value;
                else if (key == "StartupWMClass" && startupWmClass.isEmpty()) startupWmClass = value;
            }
            DesktopEntry entry;
            entry.desktopId = info.fileName();
            entry.name = name.isEmpty() ? info.completeBaseName() : name;
            entry.icon = icon;
            entry.startupWmClass = startupWmClass.isEmpty() ? info.completeBaseName() : startupWmClass;
            entries.insert(entry.desktopId, entry);
            wmToDesktop.insert(normalize(entry.startupWmClass), entry.desktopId);
            wmToDesktop.insert(normalize(info.completeBaseName()), entry.desktopId);
        }
    }
    return {entries, wmToDesktop};
}

QString resolveIconPath(const QString &iconName) {
    static QMap<QString, QString> iconCache;
    if (iconCache.contains(iconName)) {
        return iconCache.value(iconName);
    }
    const QStringList fallbackNames = {
        iconName.trimmed(),
        "application-x-executable",
        "applications-other",
        "application-default-icon",
    };
    const QStringList iconDirs = {
        QDir::homePath() + "/.local/share/icons",
        "/usr/local/share/icons",
        "/usr/share/icons",
        "/usr/share/pixmaps",
    };
    const QStringList exts = {".svg", ".png", ".xpm"};
    for (const QString &candidateName : fallbackNames) {
        if (candidateName.isEmpty()) {
            continue;
        }
        const QFileInfo explicitPath(candidateName);
        if (explicitPath.isAbsolute() && explicitPath.exists()) {
            iconCache.insert(iconName, explicitPath.absoluteFilePath());
            return explicitPath.absoluteFilePath();
        }
        for (const QString &basePath : iconDirs) {
            QDir base(basePath);
            if (!base.exists()) {
                continue;
            }
            for (const QString &ext : exts) {
                const QString direct = base.filePath(candidateName + ext);
                if (QFile::exists(direct)) {
                    iconCache.insert(iconName, direct);
                    return direct;
                }
            }
            const QStringList themeRoots = {"hicolor", "Adwaita", "Papirus", "Papirus-Dark"};
            for (const QString &themeRoot : themeRoots) {
                QDir themeDir(base.filePath(themeRoot));
                if (!themeDir.exists()) {
                    continue;
                }
                QDirIterator it(themeDir.absolutePath(), QDir::Files, QDirIterator::Subdirectories);
                while (it.hasNext()) {
                    const QString path = it.next();
                    const QFileInfo info(path);
                    if (info.completeBaseName() == candidateName && exts.contains("." + info.suffix())) {
                        iconCache.insert(iconName, path);
                        return path;
                    }
                }
            }
        }
    }
    iconCache.insert(iconName, QString());
    return {};
}

void saveState(const QJsonObject &object) {
    QDir().mkpath(cacheDirPath());
    QFile file(stateFilePath());
    if (!file.open(QIODevice::WriteOnly)) {
        return;
    }
    file.write(QJsonDocument(object).toJson(QJsonDocument::Indented));
}

QJsonObject loadState() {
    QFile file(stateFilePath());
    if (!file.open(QIODevice::ReadOnly)) {
        return {};
    }
    return QJsonDocument::fromJson(file.readAll()).object();
}

int nextFocusId(const QString &key, const QList<int> &ids, int focused) {
    if (ids.isEmpty()) {
        return 0;
    }
    QJsonObject state = loadState();
    QJsonObject lastIndex = state.value("last_index").toObject();
    int currentIndex = -1;
    if (ids.contains(focused)) {
        currentIndex = ids.indexOf(focused);
    } else {
        currentIndex = lastIndex.value(key).toInt(-1);
    }
    const int nextIndex = (currentIndex + 1) % ids.size();
    lastIndex.insert(key, nextIndex);
    state.insert("last_index", lastIndex);
    saveState(state);
    return ids.at(nextIndex);
}

void focusConIdOnWorkspace(int conId, const QString &workspace) {
    if (!workspace.isEmpty()) {
        runCommandText({"i3-msg", "workspace", workspace});
    }
    runCommandText({"i3-msg", QStringLiteral("[con_id=\"%1\"]").arg(conId), "focus"});
}

bool launchDesktop(const QString &desktopId) {
    if (runDetachedCommand({"gtk-launch", desktopId})) {
        return true;
    }
    QString desktopBase = desktopId;
    desktopBase.replace(".desktop", "");
    return runDetachedCommand({"gtk-launch", desktopBase});
}

void applyDockX11Hints(WId windowId) {
#if HANAUTA_HAS_X11
    if (windowId == 0) {
        return;
    }
    Display *display = XOpenDisplay(nullptr);
    if (display == nullptr) {
        return;
    }
    const Atom windowType = XInternAtom(display, "_NET_WM_WINDOW_TYPE", False);
    const Atom dockType = XInternAtom(display, "_NET_WM_WINDOW_TYPE_DOCK", False);
    if (windowType != None && dockType != None) {
        XChangeProperty(
            display,
            static_cast<::Window>(windowId),
            windowType,
            XA_ATOM,
            32,
            PropModeReplace,
            reinterpret_cast<const unsigned char *>(&dockType),
            1
        );
    }
    XFlush(display);
    XCloseDisplay(display);
#else
    Q_UNUSED(windowId);
#endif
}

void updateDockX11Strut(WId windowId, const QRect &geometry, bool hidden) {
#if HANAUTA_HAS_X11
    if (windowId == 0) {
        return;
    }
    Display *display = XOpenDisplay(nullptr);
    if (display == nullptr) {
        return;
    }
    const Atom strutAtom = XInternAtom(display, "_NET_WM_STRUT", False);
    const Atom strutPartialAtom = XInternAtom(display, "_NET_WM_STRUT_PARTIAL", False);

    unsigned long strut[4] = {0, 0, 0, 0};
    unsigned long strutPartial[12] = {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};

    if (!hidden) {
        const unsigned long bottom = static_cast<unsigned long>(qMax(0, geometry.height()));
        const unsigned long startX = static_cast<unsigned long>(qMax(0, geometry.x()));
        const unsigned long endX = static_cast<unsigned long>(qMax(geometry.x(), geometry.x() + geometry.width() - 1));
        strut[3] = bottom;
        strutPartial[3] = bottom;
        strutPartial[10] = startX;
        strutPartial[11] = endX;
    }

    if (strutAtom != None) {
        XChangeProperty(
            display,
            static_cast<::Window>(windowId),
            strutAtom,
            XA_CARDINAL,
            32,
            PropModeReplace,
            reinterpret_cast<const unsigned char *>(strut),
            4
        );
    }
    if (strutPartialAtom != None) {
        XChangeProperty(
            display,
            static_cast<::Window>(windowId),
            strutPartialAtom,
            XA_CARDINAL,
            32,
            PropModeReplace,
            reinterpret_cast<const unsigned char *>(strutPartial),
            12
        );
    }
    XFlush(display);
    XCloseDisplay(display);
#else
    Q_UNUSED(windowId);
    Q_UNUSED(geometry);
    Q_UNUSED(hidden);
#endif
}

struct DockItemData {
    QString itemId;
    QString name;
    QString iconPath;
    int running = 0;
    bool focused = false;
    bool pinned = false;
    QString desktopId;
    QString wmClass;
};

QList<DockItemData> buildDockItems(const DockConfig &config) {
    const QList<WindowEntry> allWindows = getOpenWindows();
    QList<WindowEntry> visibleWindows;
    for (const WindowEntry &window : allWindows) {
        if (globMatch(window.wmClass, config.blacklistWm)) {
            continue;
        }
        if (globMatch(window.title, config.blacklistWindowName)) {
            continue;
        }
        visibleWindows.append(window);
    }
    const QString focusedWorkspace = currentWorkspace();
    QMap<QString, QList<WindowEntry>> windowsByClass;
    for (const WindowEntry &window : visibleWindows) {
        windowsByClass[window.wmClass].append(window);
    }
    const auto [desktopEntries, wmToDesktop] = scanDesktopEntries();
    QMap<QString, QString> pinnedWmMap;
    for (const QString &desktopId : config.pinnedApps) {
        const DesktopEntry entry = desktopEntries.value(desktopId);
        QString desktopBase = desktopId;
        desktopBase.replace(".desktop", "");
        const QString wmClass = normalize(entry.startupWmClass.isEmpty() ? desktopBase : entry.startupWmClass);
        if (!wmClass.isEmpty()) {
            pinnedWmMap.insert(wmClass, desktopId);
        }
    }

    QList<DockItemData> items;
    auto makeDesktopItem = [&](const QString &desktopId, bool pinned) -> void {
        if (globMatch(desktopId, config.blacklistDesktop)) {
            return;
        }
        const DesktopEntry entry = desktopEntries.value(desktopId);
        QString desktopBase = desktopId;
        desktopBase.replace(".desktop", "");
        const QString wmClass = normalize(entry.startupWmClass.isEmpty() ? desktopBase : entry.startupWmClass);
        if (globMatch(wmClass, config.blacklistWm)) {
            return;
        }
        const QList<WindowEntry> runningWindows = windowsByClass.value(wmClass);
        DockItemData item;
        item.desktopId = desktopId;
        item.wmClass = wmClass;
        item.itemId = desktopId;
        item.name = entry.name.isEmpty() ? desktopBase : entry.name;
        item.iconPath = resolveIconPath(entry.icon);
        item.running = runningWindows.size();
        item.focused = std::any_of(runningWindows.begin(), runningWindows.end(), [&](const WindowEntry &window) {
            return window.workspace == focusedWorkspace;
        });
        item.pinned = pinned;
        items.append(item);
    };

    for (const QString &desktopId : config.pinnedApps) {
        makeDesktopItem(desktopId, true);
    }

    for (auto it = windowsByClass.begin(); it != windowsByClass.end(); ++it) {
        const QString wmClass = it.key();
        if (globMatch(wmClass, config.blacklistWm)) {
            continue;
        }
        QString desktopId = pinnedWmMap.value(wmClass);
        if (desktopId.isEmpty()) {
            desktopId = wmToDesktop.value(wmClass);
        }
        if (!desktopId.isEmpty() && config.pinnedApps.contains(desktopId)) {
            continue;
        }
        if (!desktopId.isEmpty() && !globMatch(desktopId, config.blacklistDesktop) && desktopEntries.contains(desktopId)) {
            makeDesktopItem(desktopId, false);
            continue;
        }
        DockItemData item;
        item.itemId = "wm:" + wmClass;
        item.name = wmClass;
        item.iconPath = resolveIconPath("application-x-executable");
        item.running = it.value().size();
        item.focused = std::any_of(it.value().begin(), it.value().end(), [&](const WindowEntry &window) {
            return window.workspace == focusedWorkspace;
        });
        item.pinned = false;
        item.wmClass = wmClass;
        items.append(item);
    }

    const int pinnedCount = std::count_if(items.begin(), items.end(), [](const DockItemData &item) { return item.pinned; });
    QList<DockItemData> pinnedItems = items.mid(0, pinnedCount);
    QList<DockItemData> runningItems = items.mid(pinnedCount);
    std::sort(runningItems.begin(), runningItems.end(), [](const DockItemData &left, const DockItemData &right) {
        if (left.focused != right.focused) {
            return left.focused;
        }
        if (left.running != right.running) {
            return left.running > right.running;
        }
        return left.name.toLower() < right.name.toLower();
    });
    pinnedItems.append(runningItems);
    return pinnedItems;
}

}  // namespace

class DockBackend final : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap palette READ palette NOTIFY paletteChanged)
    Q_PROPERTY(QVariantList items READ items NOTIFY itemsChanged)
    Q_PROPERTY(QString clockText READ clockText NOTIFY clockTextChanged)
    Q_PROPERTY(QString volumeIcon READ volumeIcon NOTIFY volumeChanged)
    Q_PROPERTY(QString volumeTooltip READ volumeTooltip NOTIFY volumeChanged)
    Q_PROPERTY(bool autoHide READ autoHide WRITE setAutoHide NOTIFY configChanged)
    Q_PROPERTY(bool iconsLeft READ iconsLeft WRITE setIconsLeft NOTIFY configChanged)
    Q_PROPERTY(QString position READ position WRITE setPosition NOTIFY configChanged)
    Q_PROPERTY(int dockWidth READ dockWidth WRITE setDockWidth NOTIFY configChanged)
    Q_PROPERTY(QString dockWidthUnit READ dockWidthUnit WRITE setDockWidthUnit NOTIFY configChanged)
    Q_PROPERTY(int itemHeight READ itemHeight WRITE setItemHeight NOTIFY configChanged)
    Q_PROPERTY(int transparency READ transparency WRITE setTransparency NOTIFY configChanged)
    Q_PROPERTY(QString materialFontFamily READ materialFontFamily CONSTANT)
    Q_PROPERTY(QString uiFontFamily READ uiFontFamily CONSTANT)
    Q_PROPERTY(QString monoFontFamily READ monoFontFamily CONSTANT)

public:
    explicit DockBackend(QObject *parent = nullptr)
        : QObject(parent),
          config_(loadDockConfig()) {
        refreshPalette();
        refreshItems();
        refreshClock();
        refreshVolume();

        connect(&paletteTimer_, &QTimer::timeout, this, &DockBackend::refreshPalette);
        paletteTimer_.start(3000);
        connect(&itemsTimer_, &QTimer::timeout, this, &DockBackend::refreshItems);
        itemsTimer_.start(1000);
        connect(&clockTimer_, &QTimer::timeout, this, &DockBackend::refreshClock);
        clockTimer_.start(1000);
        connect(&volumeTimer_, &QTimer::timeout, this, &DockBackend::refreshVolume);
        volumeTimer_.start(1500);
    }

    QVariantMap palette() const { return palette_; }
    QVariantList items() const { return items_; }
    QString clockText() const { return clockText_; }
    QString volumeIcon() const { return volumeIcon_; }
    QString volumeTooltip() const { return volumeTooltip_; }
    bool autoHide() const { return config_.autoHide; }
    bool iconsLeft() const { return config_.iconsLeft; }
    QString position() const { return config_.position; }
    int dockWidth() const { return config_.width; }
    QString dockWidthUnit() const { return config_.widthUnit; }
    int itemHeight() const { return config_.height; }
    int transparency() const { return config_.transparency; }
    QString materialFontFamily() const { return "Material Icons"; }
    QString uiFontFamily() const { return "Inter"; }
    QString monoFontFamily() const { return "JetBrains Mono"; }

    void attachWindow(QQuickWindow *window) {
        window_ = window;
        if (window_ == nullptr) {
            return;
        }
        window_->setTitle("CyberDock");
        applyDockX11Hints(window_->winId());
    }

    Q_INVOKABLE QString glyph(const QString &name) const {
        return materialGlyph(name);
    }

    Q_INVOKABLE void activateItem(const QString &itemId) {
        const QList<WindowEntry> windows = getOpenWindows();
        if (itemId.startsWith("wm:")) {
            const QString wmClass = itemId.mid(3);
            QList<int> ids;
            QString workspace;
            for (const WindowEntry &window : windows) {
                if (window.wmClass == wmClass) {
                    ids.append(window.conId);
                    if (workspace.isEmpty()) {
                        workspace = window.workspace;
                    }
                }
            }
            if (ids.isEmpty()) {
                return;
            }
            focusConIdOnWorkspace(nextFocusId("wm:" + wmClass, ids, focusedConId()), workspace);
            return;
        }

        const auto [desktopEntries, unusedMap] = scanDesktopEntries();
        const DesktopEntry entry = desktopEntries.value(itemId);
        QString desktopBase = itemId;
        desktopBase.replace(".desktop", "");
        const QString wmClass = normalize(entry.startupWmClass.isEmpty() ? desktopBase : entry.startupWmClass);
        QList<int> ids;
        QString workspace;
        for (const WindowEntry &window : windows) {
            if (window.wmClass == wmClass) {
                ids.append(window.conId);
                if (workspace.isEmpty()) {
                    workspace = window.workspace;
                }
            }
        }
        if (ids.isEmpty()) {
            launchDesktop(itemId);
            return;
        }
        focusConIdOnWorkspace(nextFocusId("did:" + itemId, ids, focusedConId()), workspace);
    }

    Q_INVOKABLE void openNewItem(const QString &itemId) {
        if (itemId.startsWith("wm:")) {
            activateItem(itemId);
            return;
        }
        launchDesktop(itemId);
    }

    Q_INVOKABLE void openLauncher() {
        const QString script = launcherScriptPath();
        if (!QFile::exists(script)) {
            return;
        }
        runDetachedCommand({pythonBinaryPath(), script});
    }

    Q_INVOKABLE void toggleMute() {
        const QString script = volumeScriptPath();
        if (QFile::exists(script)) {
            runDetachedCommand({script, "toggle-muted"});
            QTimer::singleShot(160, this, &DockBackend::refreshVolume);
        }
    }

    Q_INVOKABLE void changeVolume(int delta) {
        const QString script = volumeScriptPath();
        if (!QFile::exists(script)) {
            return;
        }
        const int current = runCommandText({script, "vol"}).toInt();
        const int next = qBound(0, current + delta, 100);
        runDetachedCommand({script, "set", QString::number(next)});
        QTimer::singleShot(160, this, &DockBackend::refreshVolume);
    }

    Q_INVOKABLE QVariantMap targetGeometry(int contentWidth, int contentHeight, bool hidden) const {
        QScreen *screen = QGuiApplication::screenAt(QCursor::pos());
        if (screen == nullptr) {
            screen = QGuiApplication::primaryScreen();
        }
        QRect area = screen ? screen->availableGeometry() : QRect(0, 0, 1280, 720);
        int width = qMax(320, contentWidth);
        if (config_.width > 0 && config_.widthUnit == "%") {
            width = qMax(320, static_cast<int>(area.width() * (config_.width / 100.0)));
            width = qMin(width, qMax(320, contentWidth));
        } else if (config_.width > 0 && config_.widthUnit == "px") {
            width = qMax(contentWidth, config_.width);
        }
        const int height = qMax(contentHeight, config_.height + 34);
        int x = area.x() + (area.width() - width) / 2;
        if (config_.position == "left") {
            x = area.x() + 16;
        } else if (config_.position == "right") {
            x = area.x() + area.width() - width - 16;
        }
        int y = area.y() + area.height() - height - 16;
        if (hidden) {
            y += qMax(0, height - 12);
        }
        return {
            {"x", x},
            {"y", y},
            {"width", width},
            {"height", height},
        };
    }

    Q_INVOKABLE void syncWindowGeometry(int x, int y, int width, int height, bool hidden) {
        if (window_ != nullptr) {
            applyDockX11Hints(window_->winId());
            updateDockX11Strut(window_->winId(), QRect(x, y, width, height), hidden);
        }
        runCommandText(
            {
                "i3-msg",
                QStringLiteral("[title=\"CyberDock\"]"),
                QStringLiteral("floating enable, sticky enable, move position %1 px %2 px, resize set %3 px %4 px")
                    .arg(x)
                    .arg(y)
                    .arg(width)
                    .arg(height),
            },
            2000
        );
    }

    Q_INVOKABLE void openDockConfig() {
        const QString path = dockConfigPath();
        if (commandExists("xdg-open")) {
            runDetachedCommand({"xdg-open", path});
            return;
        }
        const QString editor = qEnvironmentVariable("EDITOR");
        if (!editor.isEmpty()) {
            runDetachedCommand({editor, path});
        }
    }

    void setAutoHide(bool value) {
        if (config_.autoHide == value) {
            return;
        }
        config_.autoHide = value;
        persistConfig();
    }

    void setIconsLeft(bool value) {
        if (config_.iconsLeft == value) {
            return;
        }
        config_.iconsLeft = value;
        persistConfig();
    }

    void setPosition(const QString &value) {
        const QString normalized = value.trimmed().toLower();
        if (normalized.isEmpty() || config_.position == normalized) {
            return;
        }
        config_.position = normalized;
        persistConfig();
    }

    void setDockWidth(int value) {
        value = qMax(0, value);
        if (config_.width == value) {
            return;
        }
        config_.width = value;
        persistConfig();
    }

    void setDockWidthUnit(const QString &value) {
        const QString normalized = value.trimmed();
        if (normalized.isEmpty() || config_.widthUnit == normalized) {
            return;
        }
        config_.widthUnit = normalized;
        persistConfig();
    }

    void setItemHeight(int value) {
        value = qBound(64, value, 120);
        if (config_.height == value) {
            return;
        }
        config_.height = value;
        persistConfig();
    }

    void setTransparency(int value) {
        value = qBound(0, value, 100);
        if (config_.transparency == value) {
            return;
        }
        config_.transparency = value;
        refreshPalette();
        persistConfig();
    }

signals:
    void paletteChanged();
    void itemsChanged();
    void clockTextChanged();
    void volumeChanged();
    void configChanged();

private slots:
    void refreshPalette() {
        const ThemePalette theme = loadTheme();
        const qreal transparencyFactor = qBound<qreal>(0.0, config_.transparency / 100.0, 1.0);
        palette_ = {
            {"panelBg", rgba(theme.surfaceContainer, 0.92 * transparencyFactor)},
            {"panelBorder", rgba(theme.outline, 0.30 * transparencyFactor)},
            {"text", theme.onSurface},
            {"textMuted", rgba(theme.onSurfaceVariant, 0.78)},
            {"icon", theme.onSurface},
            {"hoverBg", rgba(theme.primary, 0.15)},
            {"focusedBg", rgba(theme.primary, 0.18)},
            {"focusedBorder", rgba(theme.primary, 0.30)},
            {"runningBg", rgba(theme.onSurface, 0.08)},
            {"runningBorder", rgba(theme.outline, 0.18)},
            {"dot", theme.primary},
            {"separator", rgba(theme.outline, 0.22)},
            {"shadow", rgba("#000000", 0.34)},
            {"glowStart", rgba(theme.primary, 0.24)},
            {"glowEnd", rgba(blend(theme.primary, theme.secondary, 0.36), 0.0)},
            {"utilityBg", rgba(theme.surfaceContainerHigh, 0.28)},
            {"utilityBorder", rgba(theme.outline, 0.16)},
            {"volumePill", rgba(theme.primaryContainer, 0.22)},
        };
        emit paletteChanged();
    }

    void refreshItems() {
        const QList<DockItemData> built = buildDockItems(config_);
        QVariantList nextItems;
        for (const DockItemData &item : built) {
            nextItems.append(QVariantMap{
                {"itemId", item.itemId},
                {"name", item.name},
                {"iconPath", item.iconPath.isEmpty() ? QString() : QUrl::fromLocalFile(item.iconPath).toString()},
                {"running", item.running},
                {"focused", item.focused},
                {"pinned", item.pinned},
                {"desktopId", item.desktopId},
                {"wmClass", item.wmClass},
            });
        }
        if (nextItems == items_) {
            return;
        }
        items_ = nextItems;
        emit itemsChanged();
    }

    void refreshClock() {
        const QString next = QDateTime::currentDateTime().toString("HH:mm");
        if (next == clockText_) {
            return;
        }
        clockText_ = next;
        emit clockTextChanged();
    }

    void refreshVolume() {
        const QString script = volumeScriptPath();
        if (!QFile::exists(script)) {
            return;
        }
        const int volume = runCommandText({script, "vol"}).toInt();
        const bool muted = runCommandText({script, "muted"}).trimmed().toLower() == "yes";
        QString icon = "volume_up";
        if (muted || volume == 0) icon = "volume_off";
        else if (volume <= 35) icon = "volume_mute";
        else if (volume <= 70) icon = "volume_down";
        const QString nextIcon = materialGlyph(icon);
        const QString nextTooltip = QStringLiteral("Volume %1%").arg(volume);
        if (nextIcon == volumeIcon_ && nextTooltip == volumeTooltip_) {
            return;
        }
        volumeIcon_ = nextIcon;
        volumeTooltip_ = nextTooltip;
        emit volumeChanged();
    }

private:
    void persistConfig() {
        saveDockConfig(config_);
        emit configChanged();
        refreshItems();
    }

    DockConfig config_;
    QVariantMap palette_;
    QVariantList items_;
    QString clockText_ = "--:--";
    QString volumeIcon_ = materialGlyph("volume_up");
    QString volumeTooltip_ = "Volume 0%";
    QTimer paletteTimer_;
    QTimer itemsTimer_;
    QTimer clockTimer_;
    QTimer volumeTimer_;
    QPointer<QQuickWindow> window_;
};

int main(int argc, char *argv[]) {
    QGuiApplication app(argc, argv);
    app.setApplicationName("Hanauta Dock");
    app.setDesktopFileName("HanautaDock");
    QQuickStyle::setStyle("Basic");
    loadFonts();

    const QString qmlPath = repoRoot() + "/src/service/hanauta-dock.qml";
    if (!QFile::exists(qmlPath)) {
        fprintf(stderr, "ERROR: QML file not found: %s\n", qPrintable(qmlPath));
        return 2;
    }

    DockBackend backend;
    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty("backend", &backend);
    engine.load(QUrl::fromLocalFile(qmlPath));
    if (engine.rootObjects().isEmpty()) {
        fprintf(stderr, "ERROR: failed to load QML (no root objects).\n");
        return 3;
    }
    QQuickWindow *window = qobject_cast<QQuickWindow *>(engine.rootObjects().constFirst());
    if (window != nullptr) {
        backend.attachWindow(window);
        window->show();
        QMetaObject::invokeMethod(window, "showDock");
    }
    return app.exec();
}

#include "hanauta-dock.moc"
