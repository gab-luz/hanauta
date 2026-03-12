#pragma once

#include "AuthBridge.hpp"

#include <QElapsedTimer>
#include <QPixmap>
#include <QTimer>
#include <QWidget>

#include <deque>

class AuthWindow : public QWidget {
    Q_OBJECT

public:
    explicit AuthWindow(AuthBridge *bridge, QWidget *parent = nullptr);

protected:
    void paintEvent(QPaintEvent *event) override;
    void keyPressEvent(QKeyEvent *event) override;

private slots:
    void syncTokens();

private:
    struct Token {
        int shapeIndex;
        int colorIndex;
        qint64 bornMs;
    };

    void paintBackdrop(QPainter &p);
    void paintCard(QPainter &p);
    void paintTokens(QPainter &p, const QRectF &fieldRect);
    void paintSingleToken(QPainter &p, int shapeIndex, const QPointF &center, qreal size, const QColor &color);
    QColor tokenColor(int index) const;

    AuthBridge *m_bridge;
    QPixmap m_wallpaper;
    QTimer m_animTimer;
    QElapsedTimer m_clock;
    std::deque<Token> m_tokens;
    int m_lastFailurePulse = 0;
};
