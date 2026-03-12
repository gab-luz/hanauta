#include "PamClient.hpp"

#include <QFileInfo>
#include <QStandardPaths>

namespace {
constexpr char PTYPE_INFO_MESSAGE = 'i';
constexpr char PTYPE_ERROR_MESSAGE = 'e';
constexpr char PTYPE_PROMPT_LIKE_USERNAME = 'U';
constexpr char PTYPE_PROMPT_LIKE_PASSWORD = 'P';
constexpr char PTYPE_RESPONSE_LIKE_USERNAME = 'u';
constexpr char PTYPE_RESPONSE_LIKE_PASSWORD = 'p';
}

PamClient::PamClient(QObject *parent) : QObject(parent) {
    connect(&m_process, &QProcess::readyReadStandardOutput, this, &PamClient::handleReadyRead);
    connect(&m_process, qOverload<int, QProcess::ExitStatus>(&QProcess::finished), this, &PamClient::handleFinished);
}

bool PamClient::busy() const {
    return m_busy;
}

void PamClient::authenticate(const QString &password) {
    if (m_busy) {
        return;
    }

    resetProcess();
    m_pendingPassword = password;
    m_buffer.clear();
    m_gotPrompt = false;
    m_reportedError = false;
    m_busy = true;
    emit busyChanged();

    const QString helper = resolveHelper();
    m_process.start(helper, {});
    if (!m_process.waitForStarted(3000)) {
        m_busy = false;
        emit busyChanged();
        emit authenticationFailed(QStringLiteral("Unable to start %1").arg(helper));
    }
}

void PamClient::resetProcess() {
    if (m_process.state() == QProcess::NotRunning) {
        return;
    }
    m_process.kill();
    m_process.waitForFinished(1000);
}

void PamClient::handleReadyRead() {
    m_buffer.append(m_process.readAllStandardOutput());
    while (tryConsumePacket()) {
    }
}

bool PamClient::tryConsumePacket() {
    const int headerEnd = m_buffer.indexOf('\n');
    if (headerEnd <= 0) {
        return false;
    }

    const QByteArray header = m_buffer.left(headerEnd);
    if (header.size() < 3 || header.at(1) != ' ') {
        m_buffer.clear();
        m_reportedError = true;
        emit authenticationFailed(QStringLiteral("Invalid authproto header"));
        return false;
    }

    bool ok = false;
    const int length = header.mid(2).toInt(&ok);
    if (!ok || length < 0) {
        m_buffer.clear();
        m_reportedError = true;
        emit authenticationFailed(QStringLiteral("Invalid authproto packet length"));
        return false;
    }

    const int totalSize = headerEnd + 1 + length + 1;
    if (m_buffer.size() < totalSize) {
        return false;
    }

    const char type = header.at(0);
    const QByteArray payload = m_buffer.mid(headerEnd + 1, length);
    m_buffer.remove(0, totalSize);
    const QString message = QString::fromUtf8(payload);

    switch (type) {
    case PTYPE_INFO_MESSAGE:
        emit infoMessage(message);
        break;
    case PTYPE_ERROR_MESSAGE:
        emit errorMessage(message);
        break;
    case PTYPE_PROMPT_LIKE_USERNAME:
        answerPrompt(PromptType::Username, message);
        break;
    case PTYPE_PROMPT_LIKE_PASSWORD:
        answerPrompt(PromptType::Password, message);
        break;
    default:
        break;
    }

    return true;
}

void PamClient::answerPrompt(PromptType promptType, const QString &message) {
    m_gotPrompt = true;
    if (!message.isEmpty()) {
        emit infoMessage(message);
    }

    if (promptType == PromptType::Username) {
        writePacket(PTYPE_RESPONSE_LIKE_USERNAME, QString::fromLocal8Bit(qgetenv("USER")));
        return;
    }

    writePacket(PTYPE_RESPONSE_LIKE_PASSWORD, m_pendingPassword);
}

void PamClient::writePacket(char type, const QString &message) {
    const QByteArray payload = message.toUtf8();
    QByteArray packet;
    packet.append(type);
    packet.append(' ');
    packet.append(QByteArray::number(payload.size()));
    packet.append('\n');
    packet.append(payload);
    packet.append('\n');
    m_process.write(packet);
    m_process.waitForBytesWritten(1000);
}

QString PamClient::resolveHelper() const {
    const QByteArray env = qgetenv("XSECURELOCK_AUTHPROTO");
    if (!env.isEmpty()) {
        return QString::fromLocal8Bit(env);
    }

    const QStringList candidates = {
        QStringLiteral("/usr/libexec/xsecurelock/authproto_pam"),
        QStringLiteral("/usr/lib/xsecurelock/authproto_pam"),
        QStringLiteral("authproto_pam"),
    };

    for (const QString &candidate : candidates) {
        if (candidate.contains('/')) {
            if (QFileInfo::exists(candidate) && QFileInfo(candidate).isExecutable()) {
                return candidate;
            }
            continue;
        }
        const QString resolved = QStandardPaths::findExecutable(candidate);
        if (!resolved.isEmpty()) {
            return resolved;
        }
    }

    return QStringLiteral("authproto_pam");
}

void PamClient::handleFinished(int exitCode, QProcess::ExitStatus exitStatus) {
    const bool success = exitStatus == QProcess::NormalExit && exitCode == 0;
    const bool failed = exitStatus == QProcess::NormalExit && exitCode != 0;

    m_busy = false;
    emit busyChanged();

    if (success) {
        emit authenticationSucceeded();
        return;
    }

    if (!m_reportedError) {
        QString message = QStringLiteral("Authentication failed");
        if (!m_gotPrompt) {
            message = QStringLiteral("PAM helper did not respond correctly");
        }
        emit authenticationFailed(message);
    } else if (failed) {
        emit authenticationFailed(QStringLiteral("Authentication failed"));
    }
}
