#include "AuthBridge.hpp"

#include <QCoreApplication>
#include <QDateTime>
#include <QFileInfo>
#include <QFile>
#include <QTextStream>

#include <fcntl.h>
#include <errno.h>
#include <unistd.h>

namespace {
constexpr auto kWallpaperPath = "~/.wallpapers/wallpaper.png";
}

AuthBridge::AuthBridge(QObject *parent)
    : QObject(parent),
      m_username(QString::fromLocal8Bit(qgetenv("USER"))) {
    QString wallpaper = QString::fromLocal8Bit(qgetenv("HOME")) + QStringLiteral("/.wallpapers/wallpaper.png");
    if (QFileInfo::exists(wallpaper)) {
        m_wallpaperSource = QStringLiteral("file://") + wallpaper;
    }

    const QString debugLogPath = QString::fromLocal8Bit(qgetenv("HANAUTA_AUTH_DEBUG_LOG"));
    if (!debugLogPath.isEmpty()) {
        m_debugLog.setFileName(debugLogPath);
        m_debugLog.open(QIODevice::Append | QIODevice::Text);
        logDebug(QStringLiteral("starting auth bridge pid=%1 xscreensaver_window=%2")
                     .arg(QCoreApplication::applicationPid())
                     .arg(QString::fromLocal8Bit(qgetenv("XSCREENSAVER_WINDOW"))));
    }

    const int currentFlags = fcntl(STDIN_FILENO, F_GETFL, 0);
    if (currentFlags >= 0) {
        fcntl(STDIN_FILENO, F_SETFL, currentFlags | O_NONBLOCK);
        logDebug(QStringLiteral("stdin flags set to nonblocking"));
    } else {
        logDebug(QStringLiteral("failed to read stdin flags errno=%1").arg(errno));
    }

    connect(&m_stdinPollTimer, &QTimer::timeout, this, &AuthBridge::pollStdin);
    connect(&m_clockTimer, &QTimer::timeout, this, &AuthBridge::updateClock);
    connect(&m_pamClient, &PamClient::busyChanged, this, &AuthBridge::busyChanged);
    connect(&m_pamClient, &PamClient::infoMessage, this, &AuthBridge::onInfoMessage);
    connect(&m_pamClient, &PamClient::errorMessage, this, &AuthBridge::onErrorMessage);
    connect(&m_pamClient, &PamClient::authenticationFailed, this, &AuthBridge::onAuthenticationFailed);
    connect(&m_pamClient, &PamClient::authenticationSucceeded, this, &AuthBridge::onAuthenticationSucceeded);

    m_stdinPollTimer.start(16);
    m_clockTimer.start(1000);
    updateClock();
    setStatusMessage(QStringLiteral("Enter your password"));
}

QString AuthBridge::buffer() const {
    return m_buffer;
}

bool AuthBridge::busy() const {
    return m_pamClient.busy();
}

QString AuthBridge::statusMessage() const {
    return m_statusMessage;
}

QString AuthBridge::currentTime() const {
    return m_currentTime;
}

QString AuthBridge::currentDate() const {
    return m_currentDate;
}

QString AuthBridge::username() const {
    return m_username;
}

QString AuthBridge::wallpaperSource() const {
    return m_wallpaperSource;
}

int AuthBridge::failurePulse() const {
    return m_failurePulse;
}

void AuthBridge::appendText(const QString &text) {
    if (busy() || text.isEmpty()) {
        return;
    }

    bool changed = false;
    for (const QChar ch : text) {
        if (!ch.isPrint() || ch.isSpace() && ch != QChar(' ')) {
            continue;
        }
        m_buffer.append(ch);
        changed = true;
    }

    if (changed) {
        emit bufferChanged();
        setStatusMessage(QString());
        logDebug(QStringLiteral("appendText changed buffer_len=%1 text=%2")
                     .arg(m_buffer.size())
                     .arg(QString(text).replace('\n', "\\n").replace('\r', "\\r")));
    }
}

void AuthBridge::backspace() {
    if (m_buffer.isEmpty() || busy()) {
        return;
    }
    m_buffer.chop(1);
    emit bufferChanged();
    if (m_buffer.isEmpty()) {
        setStatusMessage(QStringLiteral("Enter your password"));
    }
}

void AuthBridge::clearBuffer() {
    if (m_buffer.isEmpty() || busy()) {
        return;
    }
    m_buffer.clear();
    emit bufferChanged();
    setStatusMessage(QStringLiteral("Buffer cleared"));
}

void AuthBridge::submit() {
    if (busy()) {
        return;
    }
    if (m_buffer.isEmpty()) {
        setStatusMessage(QStringLiteral("Type something first"));
        return;
    }
    setStatusMessage(QStringLiteral("Authenticating..."));
    logDebug(QStringLiteral("submit buffer_len=%1").arg(m_buffer.size()));
    m_pamClient.authenticate(m_buffer);
}

void AuthBridge::pollStdin() {
    char bytes[128];
    const ssize_t count = ::read(STDIN_FILENO, bytes, sizeof(bytes));
    if (count < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
            return;
        }
        logDebug(QStringLiteral("stdin read error errno=%1").arg(errno));
        return;
    }
    if (count == 0) {
        return;
    }

    QByteArray raw(bytes, static_cast<int>(count));
    QString hex;
    for (unsigned char ch : raw) {
        hex += QStringLiteral("%1 ").arg(ch, 2, 16, QChar('0'));
    }
    logDebug(QStringLiteral("stdin read count=%1 hex=%2").arg(count).arg(hex.trimmed()));

    for (ssize_t i = 0; i < count; ++i) {
        const unsigned char byte = static_cast<unsigned char>(bytes[i]);
        if (byte == '\n' || byte == '\r') {
            submit();
            continue;
        }
        if (byte == 0x7f || byte == '\b') {
            backspace();
            continue;
        }
        if (byte == 0x15 || byte == 0x1b) {
            clearBuffer();
            continue;
        }
        if (!isAcceptedInput(static_cast<char>(byte)) || busy()) {
            continue;
        }
        appendText(QString(QChar(byte)));
    }
}

void AuthBridge::updateClock() {
    const QDateTime now = QDateTime::currentDateTime();
    const QString nextTime = now.toString(QStringLiteral("HH:mm"));
    const QString nextDate = now.toString(QStringLiteral("dddd • dd MMMM yyyy"));

    if (nextTime != m_currentTime || nextDate != m_currentDate) {
        m_currentTime = nextTime;
        m_currentDate = nextDate;
        emit timeChanged();
    }
}

void AuthBridge::onInfoMessage(const QString &message) {
    if (!message.isEmpty()) {
        setStatusMessage(message);
    }
}

void AuthBridge::onErrorMessage(const QString &message) {
    if (!message.isEmpty()) {
        setStatusMessage(message);
    }
}

void AuthBridge::onAuthenticationFailed(const QString &message) {
    m_buffer.clear();
    emit bufferChanged();
    ++m_failurePulse;
    emit failurePulseChanged();
    logDebug(QStringLiteral("authentication failed message=%1").arg(message));
    setStatusMessage(message.isEmpty() ? QStringLiteral("Authentication failed") : message);
}

void AuthBridge::onAuthenticationSucceeded() {
    logDebug(QStringLiteral("authentication succeeded"));
    setStatusMessage(QStringLiteral("Unlocked"));
    emit requestQuit(0);
}

void AuthBridge::appendCharacter(QChar ch) {
    m_buffer.append(ch);
    emit bufferChanged();
    setStatusMessage(QString());
}

void AuthBridge::setStatusMessage(const QString &message) {
    const QString normalized = message.isEmpty() ? QStringLiteral(" ") : message;
    if (normalized == m_statusMessage) {
        return;
    }
    m_statusMessage = normalized;
    emit statusMessageChanged();
}

bool AuthBridge::isAcceptedInput(char byte) {
    return byte >= 0x20 && byte <= 0x7e;
}

void AuthBridge::logDebug(const QString &message) {
    if (!m_debugLog.isOpen()) {
        return;
    }

    QTextStream stream(&m_debugLog);
    stream << QDateTime::currentDateTime().toString(QStringLiteral("HH:mm:ss.zzz "))
           << message << '\n';
    stream.flush();
}
