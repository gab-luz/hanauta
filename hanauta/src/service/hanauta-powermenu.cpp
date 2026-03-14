#include <QFile>
#include <QDir>
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QProcess>
#include <QCoreApplication>
#include <QStringList>
#include <QStandardPaths>
#include <QString>
#include <QTimer>
#include <QUrl>
#include <QFontDatabase>
#include <QObject>

#include <cstdio>
#include <cstdlib>
#include <pwd.h>
#include <sys/types.h>
#include <unistd.h>

namespace {

QString commandPath(const QString &command) {
    return QStandardPaths::findExecutable(command);
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
        return "unknown";
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

QString currentUsername() {
    if (const char *envUser = std::getenv("USER"); envUser && *envUser) {
        return QString::fromUtf8(envUser);
    }
    if (passwd *pwd = getpwuid(getuid()); pwd && pwd->pw_name) {
        return QString::fromUtf8(pwd->pw_name);
    }
    return "user";
}

bool spawnDetached(const QStringList &command, QString *error = nullptr) {
    if (command.isEmpty()) {
        if (error) {
            *error = "Invalid command.";
        }
        return false;
    }
    const QString executable = commandPath(command.first());
    if (executable.isEmpty()) {
        if (error) {
            *error = QStringLiteral("Command not found: %1").arg(command.first());
        }
        return false;
    }
    if (!QProcess::startDetached(executable, command.mid(1))) {
        if (error) {
            *error = QStringLiteral("Failed to run: %1").arg(command.join(' '));
        }
        return false;
    }
    return true;
}

void loadAppFonts(const QString &repoRoot) {
    const QStringList fonts = {
        repoRoot + "/assets/fonts/MaterialSymbolsRounded.ttf",
        repoRoot + "/assets/fonts/MaterialSymbolsOutlined.ttf",
        repoRoot + "/assets/fonts/MaterialIcons-Regular.ttf",
        repoRoot + "/assets/fonts/MaterialIconsOutlined-Regular.otf",
        repoRoot + "/assets/fonts/InterVariable.ttf",
        repoRoot + "/assets/fonts/Outfit-VariableFont_wght.ttf",
    };
    for (const QString &path : fonts) {
        if (QFile::exists(path)) {
            QFontDatabase::addApplicationFont(path);
        }
    }
}

}  // namespace

class Backend final : public QObject {
    Q_OBJECT
    Q_PROPERTY(QString username READ username NOTIFY usernameChanged)
    Q_PROPERTY(QString uptime READ uptime NOTIFY uptimeChanged)

public:
    explicit Backend(QObject *parent = nullptr)
        : QObject(parent),
          username_(currentUsername()),
          uptime_(formatUptime(readUptimeSeconds())) {
        uptimeTimer_.setInterval(30000);
        connect(&uptimeTimer_, &QTimer::timeout, this, &Backend::refreshUptime);
        uptimeTimer_.start();
    }

    QString username() const { return username_; }
    QString uptime() const { return uptime_; }

    Q_INVOKABLE void close() {
        QGuiApplication::quit();
    }

    Q_INVOKABLE void perform(const QString &action) {
        const QString normalized = action.trimmed().toLower();
        if (normalized.isEmpty()) {
            emit notify("Invalid action.");
            return;
        }

        QString message;
        bool ok = false;
        if (normalized == "shutdown") {
            ok = tryCommands({{"systemctl", "poweroff"}, {"loginctl", "poweroff"}, {"poweroff"}}, &message, "Shutting down...");
        } else if (normalized == "restart") {
            ok = tryCommands({{"systemctl", "reboot"}, {"loginctl", "reboot"}, {"reboot"}}, &message, "Restarting...");
        } else if (normalized == "sleep") {
            ok = tryCommands({{"systemctl", "suspend"}, {"loginctl", "suspend"}}, &message, "Suspending...");
        } else if (normalized == "logout") {
            QStringList candidates;
            const QString sessionId = QString::fromUtf8(qgetenv("XDG_SESSION_ID")).trimmed();
            QList<QStringList> commands = {{"i3-msg", "exit"}, {"bspc", "quit"}};
            if (!sessionId.isEmpty()) {
                commands.append({"loginctl", "terminate-session", sessionId});
            }
            ok = tryCommands(commands, &message, "Logging out...");
        } else {
            emit notify(QStringLiteral("Unknown action: %1").arg(normalized));
            return;
        }

        if (ok) {
            emit notify(message);
            QTimer::singleShot(200, qApp, &QGuiApplication::quit);
        } else {
            emit notify(message);
        }
    }

signals:
    void notify(const QString &message);
    void usernameChanged();
    void uptimeChanged();

private:
    void refreshUptime() {
        const QString next = formatUptime(readUptimeSeconds());
        if (next == uptime_) {
            return;
        }
        uptime_ = next;
        emit uptimeChanged();
    }

    bool tryCommands(const QList<QStringList> &commands, QString *message, const QString &successMessage) {
        for (const QStringList &command : commands) {
            QString error;
            if (spawnDetached(command, &error)) {
                if (message) {
                    *message = successMessage;
                }
                return true;
            }
            if (message && !error.isEmpty()) {
                *message = error;
            }
        }
        if (message && message->isEmpty()) {
            *message = "No supported command found.";
        }
        return false;
    }

    QString username_;
    QString uptime_;
    QTimer uptimeTimer_;
};

int main(int argc, char *argv[]) {
    QGuiApplication app(argc, argv);
    app.setApplicationName("Hanauta Power Menu");
    app.setDesktopFileName("HanautaPowerMenu");

    const QString appDir = QCoreApplication::applicationDirPath();
    const QString repoRoot = QDir(appDir + "/..").absolutePath();
    loadAppFonts(repoRoot);

    const QString qmlPath = repoRoot + "/src/pyqt/powermenu/powermenu.qml";
    if (!QFile::exists(qmlPath)) {
        fprintf(stderr, "ERROR: QML file not found: %s\n", qPrintable(qmlPath));
        return 2;
    }

    QQmlApplicationEngine engine;
    Backend backend;
    engine.rootContext()->setContextProperty("backend", &backend);
    engine.load(QUrl::fromLocalFile(qmlPath));
    if (engine.rootObjects().isEmpty()) {
        fprintf(stderr, "ERROR: failed to load QML (no root objects).\n");
        return 3;
    }

    return app.exec();
}

#include "hanauta-powermenu.moc"
