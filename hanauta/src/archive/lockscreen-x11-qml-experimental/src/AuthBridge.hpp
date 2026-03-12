#pragma once

#include "PamClient.hpp"

#include <QFile>
#include <QObject>
#include <QTimer>

class AuthBridge : public QObject {
    Q_OBJECT
    Q_PROPERTY(QString buffer READ buffer NOTIFY bufferChanged)
    Q_PROPERTY(bool busy READ busy NOTIFY busyChanged)
    Q_PROPERTY(QString statusMessage READ statusMessage NOTIFY statusMessageChanged)
    Q_PROPERTY(QString currentTime READ currentTime NOTIFY timeChanged)
    Q_PROPERTY(QString currentDate READ currentDate NOTIFY timeChanged)
    Q_PROPERTY(QString username READ username CONSTANT)
    Q_PROPERTY(QString wallpaperSource READ wallpaperSource CONSTANT)
    Q_PROPERTY(int failurePulse READ failurePulse NOTIFY failurePulseChanged)

public:
    explicit AuthBridge(QObject *parent = nullptr);

    QString buffer() const;
    bool busy() const;
    QString statusMessage() const;
    QString currentTime() const;
    QString currentDate() const;
    QString username() const;
    QString wallpaperSource() const;
    int failurePulse() const;

signals:
    void bufferChanged();
    void busyChanged();
    void statusMessageChanged();
    void timeChanged();
    void failurePulseChanged();
    void requestQuit(int exitCode);

public slots:
    void appendText(const QString &text);
    void backspace();
    void clearBuffer();
    void submit();

private slots:
    void pollStdin();
    void updateClock();
    void onInfoMessage(const QString &message);
    void onErrorMessage(const QString &message);
    void onAuthenticationFailed(const QString &message);
    void onAuthenticationSucceeded();

private:
    void appendCharacter(QChar ch);
    void setStatusMessage(const QString &message);
    static bool isAcceptedInput(char byte);
    void logDebug(const QString &message);

    QString m_buffer;
    QString m_statusMessage;
    QString m_currentTime;
    QString m_currentDate;
    QString m_username;
    QString m_wallpaperSource;
    int m_failurePulse = 0;
    QTimer m_stdinPollTimer;
    QTimer m_clockTimer;
    PamClient m_pamClient;
    QFile m_debugLog;
};
