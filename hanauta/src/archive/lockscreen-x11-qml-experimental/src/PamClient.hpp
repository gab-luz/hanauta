#pragma once

#include <QObject>
#include <QProcess>

class PamClient : public QObject {
    Q_OBJECT

public:
    explicit PamClient(QObject *parent = nullptr);

    bool busy() const;
    void authenticate(const QString &password);

signals:
    void busyChanged();
    void infoMessage(const QString &message);
    void errorMessage(const QString &message);
    void authenticationFailed(const QString &message);
    void authenticationSucceeded();

private:
    enum class PromptType {
        Username,
        Password,
    };

    void resetProcess();
    void handleReadyRead();
    void handleFinished(int exitCode, QProcess::ExitStatus exitStatus);
    bool tryConsumePacket();
    void writePacket(char type, const QString &message);
    QString resolveHelper() const;
    void answerPrompt(PromptType promptType, const QString &message);

    QProcess m_process;
    QByteArray m_buffer;
    QString m_pendingPassword;
    bool m_busy = false;
    bool m_gotPrompt = false;
    bool m_reportedError = false;
};
