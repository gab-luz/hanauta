#include <QGuiApplication>
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
#include <QProcess>
#include <QQuickStyle>
#include <QTimer>
#include <QVariant>
#include <QtQml>
#include <memory>
#include <vector>
#include <algorithm>

namespace {

QString paletteFilePath() {
    return QDir::homePath() + "/.local/state/hanauta/theme/pyqt_palette.json";
}

QString dataFilePath() {
    return QDir::homePath() + "/.local/state/hanauta/study-tracker/data.json";
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

QJsonObject loadPaletteJson() {
    QFile file(paletteFilePath());
    if (!file.open(QIODevice::ReadOnly)) {
        return {};
    }
    return QJsonDocument::fromJson(file.readAll()).object();
}

QJsonObject loadDataJson() {
    QFile file(dataFilePath());
    if (!file.open(QIODevice::ReadOnly)) {
        return QJsonObject();
    }
    return QJsonDocument::fromJson(file.readAll()).object();
}

void saveDataJson(const QJsonObject &obj) {
    QFile file(dataFilePath());
    if (file.open(QIODevice::WriteOnly)) {
        file.write(QJsonDocument(obj).toJson(QJsonDocument::Indented));
    }
}

QString formatDuration(int minutes) {
    if (minutes < 60) {
        return QStringLiteral("%1m").arg(minutes);
    }
    const int hours = minutes / 60;
    const int mins = minutes % 60;
    if (mins == 0) {
        return QStringLiteral("%1h").arg(hours);
    }
    return QStringLiteral("%1h %2m").arg(hours).arg(mins);
}

QString formatDisplayDate(const QDate &date) {
    const QDate today = QDate::currentDate();
    const QDate yesterday = today.addDays(-1);
    if (date == today) return "Today";
    if (date == yesterday) return "Yesterday";
    return date.toString("MMM d");
}

}  // namespace

class StudySession {
public:
    QString id;
    QString subject;
    QString type;
    int durationMinutes;
    QDateTime startTime;
    QString notes;

    QJsonObject toJson() const {
        QJsonObject obj;
        obj["id"] = id;
        obj["subject"] = subject;
        obj["type"] = type;
        obj["duration_minutes"] = durationMinutes;
        obj["start_time"] = startTime.toString(Qt::ISODate);
        obj["notes"] = notes;
        return obj;
    }

    static StudySession fromJson(const QJsonObject &obj) {
        StudySession session;
        session.id = obj["id"].toString();
        session.subject = obj["subject"].toString();
        session.type = obj["type"].toString();
        session.durationMinutes = obj["duration_minutes"].toInt();
        session.startTime = QDateTime::fromString(obj["start_time"].toString(), Qt::ISODate);
        session.notes = obj["notes"].toString();
        return session;
    }
};

class SubjectStats {
public:
    QString name;
    QString type;
    int totalMinutes = 0;
    int sessionCount = 0;
    QDate lastSessionDate;

    QJsonObject toJson() const {
        QJsonObject obj;
        obj["name"] = name;
        obj["type"] = type;
        obj["total_minutes"] = totalMinutes;
        obj["session_count"] = sessionCount;
        obj["last_session_date"] = lastSessionDate.toString(Qt::ISODate);
        return obj;
    }
};

class StudyTrackerBackend : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap palette READ palette NOTIFY paletteChanged)
    Q_PROPERTY(QVariantList subjects READ subjects NOTIFY subjectsChanged)
    Q_PROPERTY(QVariantList recentSessions READ recentSessions NOTIFY sessionsChanged)
    Q_PROPERTY(QVariantList todaySessions READ todaySessions NOTIFY sessionsChanged)
    Q_PROPERTY(int todayMinutes READ todayMinutes NOTIFY sessionsChanged)
    Q_PROPERTY(int weekMinutes READ weekMinutes NOTIFY sessionsChanged)
    Q_PROPERTY(QString currentSubject READ currentSubject WRITE setCurrentSubject NOTIFY currentSubjectChanged)
    Q_PROPERTY(QString currentType READ currentType WRITE setCurrentType NOTIFY currentTypeChanged)
    Q_PROPERTY(bool isTracking READ isTracking NOTIFY trackingChanged)
    Q_PROPERTY(int elapsedSeconds READ elapsedSeconds NOTIFY trackingChanged)
    Q_PROPERTY(QString materialFontFamily READ materialFontFamily CONSTANT)

public:
    explicit StudyTrackerBackend(QObject *parent = nullptr)
        : QObject(parent) {
        loadData();
        refreshPalette();
        
        connect(&paletteTimer_, &QTimer::timeout, this, &StudyTrackerBackend::refreshPalette);
        paletteTimer_.start(5000);
        
        connect(&trackingTimer_, &QTimer::timeout, this, &StudyTrackerBackend::updateTracking);
    }

    QVariantMap palette() const {
        return palette_;
    }

    QVariantList subjects() const {
        QVariantList result;
        for (const auto &s : subjects_) {
            QVariantMap obj;
            obj["name"] = s.name;
            obj["type"] = s.type;
            obj["total_minutes"] = s.totalMinutes;
            obj["session_count"] = s.sessionCount;
            result.append(obj);
        }
        return result;
    }

    QVariantList recentSessions() const {
        QVariantList result;
        const int count = qMin(10, static_cast<int>(sessions_.size()));
        for (int i = 0; i < count; ++i) {
            const auto &s = sessions_[i];
            QVariantMap obj;
            obj["id"] = s.id;
            obj["subject"] = s.subject;
            obj["type"] = s.type;
            obj["duration"] = formatDuration(s.durationMinutes);
            obj["display_date"] = formatDisplayDate(s.startTime.date());
            obj["start_time"] = s.startTime.toString("HH:mm");
            result.append(obj);
        }
        return result;
    }

    QVariantList todaySessions() const {
        QVariantList result;
        const QDate today = QDate::currentDate();
        for (const auto &s : sessions_) {
            if (s.startTime.date() == today) {
                QVariantMap obj;
                obj["id"] = s.id;
                obj["subject"] = s.subject;
                obj["type"] = s.type;
                obj["duration"] = formatDuration(s.durationMinutes);
                obj["start_time"] = s.startTime.toString("HH:mm");
                result.append(obj);
            }
        }
        return result;
    }

    int todayMinutes() const {
        int total = 0;
        const QDate today = QDate::currentDate();
        for (const auto &s : sessions_) {
            if (s.startTime.date() == today) {
                total += s.durationMinutes;
            }
        }
        return total;
    }

    int weekMinutes() const {
        int total = 0;
        const QDate today = QDate::currentDate();
        const QDate weekAgo = today.addDays(-7);
        for (const auto &s : sessions_) {
            if (s.startTime.date() >= weekAgo && s.startTime.date() <= today) {
                total += s.durationMinutes;
            }
        }
        return total;
    }

    QString currentSubject() const { return currentSubject_; }
    void setCurrentSubject(const QString &subject) {
        if (currentSubject_ != subject) {
            currentSubject_ = subject;
            emit currentSubjectChanged();
        }
    }

    QString currentType() const { return currentType_; }
    void setCurrentType(const QString &type) {
        if (currentType_ != type) {
            currentType_ = type;
            emit currentTypeChanged();
        }
    }

    bool isTracking() const { return isTracking_; }

    int elapsedSeconds() const {
        if (!isTracking_) return 0;
        return trackingStartTime_.secsTo(QDateTime::currentDateTime());
    }

    Q_INVOKABLE void startTracking() {
        if (isTracking_ || currentSubject_.isEmpty()) return;
        
        isTracking_ = true;
        trackingStartTime_ = QDateTime::currentDateTime();
        trackingTimer_.start(1000);
        emit trackingChanged();
    }

    Q_INVOKABLE void stopTracking() {
        if (!isTracking_) return;
        
        trackingTimer_.stop();
        
        const int elapsedSecs = trackingStartTime_.secsTo(QDateTime::currentDateTime());
        const int durationMins = qMax(1, elapsedSecs / 60);
        
        StudySession session;
        session.id = QUuid::createUuid().toString(QUuid::WithoutBraces);
        session.subject = currentSubject_;
        session.type = currentType_;
        session.durationMinutes = durationMins;
        session.startTime = trackingStartTime_;
        
        sessions_.insert(sessions_.begin(), session);
        updateSubjectStats(session);
        saveData();
        
        isTracking_ = false;
        emit trackingChanged();
        emit sessionsChanged();
    }

    Q_INVOKABLE void deleteSession(const QString &sessionId) {
        for (auto it = sessions_.begin(); it != sessions_.end(); ++it) {
            if (it->id == sessionId) {
                sessions_.erase(it);
                recalculateStats();
                saveData();
                emit sessionsChanged();
                break;
            }
        }
    }

    Q_INVOKABLE void addSubject(const QString &name, const QString &type) {
        for (const auto &s : subjects_) {
            if (s.name == name) return;
        }
        
        SubjectStats subject;
        subject.name = name;
        subject.type = type;
        subjects_.push_back(subject);
        saveData();
        emit subjectsChanged();
    }

    Q_INVOKABLE void removeSubject(const QString &name) {
        subjects_.erase(
            std::remove_if(subjects_.begin(), subjects_.end(), [&](const SubjectStats &s) { return s.name == name; }),
            subjects_.end());
        saveData();
        emit subjectsChanged();
    }

    Q_INVOKABLE void quit() {
        if (isTracking_) {
            stopTracking();
        }
        QCoreApplication::quit();
    }

    Q_INVOKABLE QString materialIcon(const QString &name) const {
        static const QHash<QString, QString> icons = {
            {"language", "translate"},
            {"code", "code"},
            {"book", "menu_book"},
            {"timer", "timer"},
            {"play", "play_arrow"},
            {"stop", "stop"},
            {"delete", "delete"},
            {"add", "add"},
            {"settings", "settings"},
            {"close", "close"},
            {"japanese", "translate"},
            {"spanish", "translate"},
            {"programming", "code"},
            {"study", "school"},
        };
        return icons.value(name, name);
    }

    QString materialFontFamily() const {
        return "Material Symbols Rounded";
    }

signals:
    void paletteChanged();
    void subjectsChanged();
    void sessionsChanged();
    void currentSubjectChanged();
    void currentTypeChanged();
    void trackingChanged();

private slots:
    void refreshPalette() {
        const QJsonObject obj = loadPaletteJson();
        const bool useMatugen = obj.value("use_matugen").toBool(false);
        
        QVariantMap p;
        
        if (useMatugen) {
            p["primary"] = normalizeHex(obj.value("primary").toString("#D0BCFF"), "#D0BCFF");
            p["onPrimary"] = normalizeHex(obj.value("on_primary").toString("#381E72"), "#381E72");
            p["primaryContainer"] = normalizeHex(obj.value("primary_container").toString("#4F378B"), "#4F378B");
            p["onPrimaryContainer"] = normalizeHex(obj.value("on_primary_container").toString("#EADDFF"), "#EADDFF");
            p["secondary"] = normalizeHex(obj.value("secondary").toString("#CCC2DC"), "#CCC2DC");
            p["onSecondary"] = normalizeHex(obj.value("on_secondary").toString("#332D41"), "#332D41");
            p["tertiary"] = normalizeHex(obj.value("tertiary").toString("#EFB8C8"), "#EFB8C8");
            p["onTertiary"] = normalizeHex(obj.value("on_tertiary").toString("#492532"), "#492532");
            p["background"] = normalizeHex(obj.value("background").toString("#141218"), "#141218");
            p["onBackground"] = normalizeHex(obj.value("on_background").toString("#E6E0E9"), "#E6E0E9");
            p["surface"] = normalizeHex(obj.value("surface").toString("#141218"), "#141218");
            p["onSurface"] = normalizeHex(obj.value("on_surface").toString("#E6E0E9"), "#E6E0E9");
            p["surfaceContainer"] = normalizeHex(obj.value("surface_container").toString("#211F26"), "#211F26");
            p["surfaceContainerHigh"] = normalizeHex(obj.value("surface_container_high").toString("#2B2930"), "#2B2930");
            p["surfaceVariant"] = normalizeHex(obj.value("surface_variant").toString("#49454F"), "#49454F");
            p["onSurfaceVariant"] = normalizeHex(obj.value("on_surface_variant").toString("#CAC4D0"), "#CAC4D0");
            p["outline"] = normalizeHex(obj.value("outline").toString("#938F99"), "#938F99");
            p["error"] = normalizeHex(obj.value("error").toString("#F2B8B5"), "#F2B8B5");
            p["onError"] = normalizeHex(obj.value("on_error").toString("#601410"), "#601410");
        } else {
            p["primary"] = "#D0BCFF";
            p["onPrimary"] = "#381E72";
            p["primaryContainer"] = "#4F378B";
            p["onPrimaryContainer"] = "#EADDFF";
            p["secondary"] = "#CCC2DC";
            p["onSecondary"] = "#332D41";
            p["tertiary"] = "#EFB8C8";
            p["onTertiary"] = "#492532";
            p["background"] = "#141218";
            p["onBackground"] = "#E6E0E9";
            p["surface"] = "#141218";
            p["onSurface"] = "#E6E0E9";
            p["surfaceContainer"] = "#211F26";
            p["surfaceContainerHigh"] = "#2B2930";
            p["surfaceVariant"] = "#49454F";
            p["onSurfaceVariant"] = "#CAC4D0";
            p["outline"] = "#938F99";
            p["error"] = "#F2B8B5";
            p["onError"] = "#601410";
        }
        
        p["panelBg"] = p["surfaceContainer"].toString() + "D6";
        p["panelBorder"] = p["outline"].toString() + "47";
        p["accentSoft"] = p["primary"].toString() + "2E";
        p["text"] = p["onSurface"].toString();
        p["textMuted"] = p["onSurfaceVariant"].toString() + "C7";
        p["icon"] = p["text"].toString();
        
        palette_ = p;
        emit paletteChanged();
    }

private:
    void loadData() {
        const QJsonObject data = loadDataJson();
        
        const QJsonArray subjectsArray = data.value("subjects").toArray();
        for (const auto &v : subjectsArray) {
            const QJsonObject obj = v.toObject();
            SubjectStats s;
            s.name = obj["name"].toString();
            s.type = obj["type"].toString();
            s.totalMinutes = obj["total_minutes"].toInt();
            s.sessionCount = obj["session_count"].toInt();
            s.lastSessionDate = QDate::fromString(obj["last_session_date"].toString(), Qt::ISODate);
            subjects_.push_back(s);
        }
        
        const QJsonArray sessionsArray = data.value("sessions").toArray();
        for (const auto &v : sessionsArray) {
            sessions_.push_back(StudySession::fromJson(v.toObject()));
        }
        
        if (subjects_.empty()) {
            addSubject("Japanese", "language");
            addSubject("Spanish", "language");
            addSubject("Programming", "programming");
            addSubject("Rust", "programming");
        }
        
        if (!subjects_.empty()) {
            currentSubject_ = subjects_.front().name;
            currentType_ = subjects_.front().type;
        }
    }

    void saveData() {
        QJsonObject data;
        
        QJsonArray subjectsArray;
        for (const auto &s : subjects_) {
            subjectsArray.append(s.toJson());
        }
        data["subjects"] = subjectsArray;
        
        QJsonArray sessionsArray;
        for (const auto &s : sessions_) {
            sessionsArray.append(s.toJson());
        }
        data["sessions"] = sessionsArray;
        
        saveDataJson(data);
    }

    void updateSubjectStats(const StudySession &session) {
        for (auto &s : subjects_) {
            if (s.name == session.subject) {
                s.totalMinutes += session.durationMinutes;
                s.sessionCount++;
                s.lastSessionDate = session.startTime.date();
                break;
            }
        }
        emit subjectsChanged();
    }

    void recalculateStats() {
        for (auto &s : subjects_) {
            s.totalMinutes = 0;
            s.sessionCount = 0;
            s.lastSessionDate = QDate();
        }
        
        for (const auto &session : sessions_) {
            for (auto &s : subjects_) {
                if (s.name == session.subject) {
                    s.totalMinutes += session.durationMinutes;
                    s.sessionCount++;
                    if (!s.lastSessionDate.isValid() || session.startTime.date() > s.lastSessionDate) {
                        s.lastSessionDate = session.startTime.date();
                    }
                    break;
                }
            }
        }
        emit subjectsChanged();
    }

    void updateTracking() {
        emit trackingChanged();
    }

    QVariantMap palette_;
    std::vector<SubjectStats> subjects_;
    std::vector<StudySession> sessions_;
    QString currentSubject_;
    QString currentType_;
    bool isTracking_ = false;
    QDateTime trackingStartTime_;
    QTimer paletteTimer_;
    QTimer trackingTimer_;
};

int main(int argc, char *argv[]) {
    QGuiApplication app(argc, argv);
    app.setApplicationName("Hanauta Study Tracker");
    app.setDesktopFileName("HanautaStudyTracker");

    const QString appDir = QCoreApplication::applicationDirPath();
    const QString repoRoot = QDir(appDir + "/..").absolutePath();
    
    const QStringList fonts = {
        repoRoot + "/assets/fonts/MaterialSymbolsRounded.ttf",
        repoRoot + "/assets/fonts/MaterialSymbolsOutlined.ttf",
        repoRoot + "/assets/fonts/MaterialIcons-Regular.ttf",
        repoRoot + "/assets/fonts/InterVariable.ttf",
        repoRoot + "/assets/fonts/Outfit-VariableFont_wght.ttf",
    };
    for (const QString &path : fonts) {
        if (QFile::exists(path)) {
            QFontDatabase::addApplicationFont(path);
        }
    }

    const QString qmlPath = repoRoot + "/src/service/hanauta-study-tracker.qml";
    if (!QFile::exists(qmlPath)) {
        fprintf(stderr, "ERROR: QML file not found: %s\n", qPrintable(qmlPath));
        return 2;
    }

    qmlRegisterType<StudyTrackerBackend>("Hanauta.StudyTracker", 1, 0, "StudyTrackerBackend");

    QQmlApplicationEngine engine;
    StudyTrackerBackend backend;
    engine.rootContext()->setContextProperty("backend", &backend);
    engine.load(QUrl::fromLocalFile(qmlPath));

    if (engine.rootObjects().isEmpty()) {
        fprintf(stderr, "ERROR: failed to load QML (no root objects).\n");
        return 3;
    }

    return app.exec();
}

#include "hanauta-study-tracker.moc"
