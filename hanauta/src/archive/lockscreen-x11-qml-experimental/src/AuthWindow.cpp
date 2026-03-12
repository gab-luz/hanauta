#include "AuthWindow.hpp"

#include <QKeyEvent>
#include <QPainter>
#include <QPainterPath>
#include <QPaintEvent>

namespace {
QColor kTextMain("#f1e8ff");
QColor kTextSub("#d4c6eb");
QColor kTextDim("#9f8fb8");
QColor kAccent("#c8b6ff");
QColor kCardBg(27, 21, 38, 232);
QColor kCardShadow(0, 0, 0, 72);
QColor kFieldBg(32, 24, 45, 255);
QColor kFieldBorder(255, 255, 255, 24);
QColor kError("#ffb4ab");
QColor kShapes[] = {QColor("#c8b6ff"), QColor("#8ec5ff"), QColor("#93e9be"), QColor("#ffcf90")};
}

AuthWindow::AuthWindow(AuthBridge *bridge, QWidget *parent)
    : QWidget(parent), m_bridge(bridge) {
    setAttribute(Qt::WA_TranslucentBackground, true);
    setFocusPolicy(Qt::StrongFocus);

    const QString wallpaperPath = m_bridge->wallpaperSource().startsWith("file://")
        ? m_bridge->wallpaperSource().mid(QStringLiteral("file://").size())
        : QString();
    if (!wallpaperPath.isEmpty()) {
        m_wallpaper.load(wallpaperPath);
    }

    m_clock.start();
    m_animTimer.setInterval(16);
    connect(&m_animTimer, &QTimer::timeout, this, qOverload<>(&AuthWindow::update));
    m_animTimer.start();

    connect(m_bridge, &AuthBridge::bufferChanged, this, &AuthWindow::syncTokens);
    connect(m_bridge, &AuthBridge::timeChanged, this, qOverload<>(&AuthWindow::update));
    connect(m_bridge, &AuthBridge::statusMessageChanged, this, qOverload<>(&AuthWindow::update));
    connect(m_bridge, &AuthBridge::busyChanged, this, qOverload<>(&AuthWindow::update));
    connect(m_bridge, &AuthBridge::failurePulseChanged, this, [this] {
        m_lastFailurePulse = m_bridge->failurePulse();
        update();
    });

    syncTokens();
}

void AuthWindow::paintEvent(QPaintEvent *event) {
    Q_UNUSED(event);

    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing, true);
    p.setRenderHint(QPainter::SmoothPixmapTransform, true);

    paintBackdrop(p);
    paintCard(p);
}

void AuthWindow::keyPressEvent(QKeyEvent *event) {
    if (event->key() == Qt::Key_Return || event->key() == Qt::Key_Enter) {
        m_bridge->submit();
        event->accept();
        return;
    }
    if (event->key() == Qt::Key_Backspace) {
        m_bridge->backspace();
        event->accept();
        return;
    }
    if (event->key() == Qt::Key_Escape) {
        m_bridge->clearBuffer();
        event->accept();
        return;
    }
    if (!event->text().isEmpty()) {
        m_bridge->appendText(event->text());
        event->accept();
        return;
    }
    QWidget::keyPressEvent(event);
}

void AuthWindow::syncTokens() {
    const int target = m_bridge->buffer().size();
    const qint64 now = m_clock.elapsed();
    while (static_cast<int>(m_tokens.size()) < target) {
        const int index = static_cast<int>(m_tokens.size());
        m_tokens.push_back(Token{index % 4, index % 4, now});
    }
    while (static_cast<int>(m_tokens.size()) > target) {
        m_tokens.pop_back();
    }
    update();
}

void AuthWindow::paintBackdrop(QPainter &p) {
    if (!m_wallpaper.isNull()) {
        const QPixmap scaled = m_wallpaper.scaled(size(), Qt::KeepAspectRatioByExpanding, Qt::SmoothTransformation);
        const int x = (width() - scaled.width()) / 2;
        const int y = (height() - scaled.height()) / 2;
        p.drawPixmap(x, y, scaled);
    } else {
        p.fillRect(rect(), QColor("#09070d"));
    }

    QLinearGradient overlay(0, 0, 0, height());
    overlay.setColorAt(0.0, QColor(6, 6, 11, 50));
    overlay.setColorAt(1.0, QColor(6, 6, 11, 92));
    p.fillRect(rect(), overlay);
}

void AuthWindow::paintCard(QPainter &p) {
    const QRectF card((width() - 560) / 2.0, (height() - 420) / 2.0, 560, 420);
    const QRectF shadowRect = card.translated(10, 14);

    p.setPen(Qt::NoPen);
    p.setBrush(kCardShadow);
    p.drawRoundedRect(shadowRect, 28, 28);

    p.setBrush(kCardBg);
    p.setPen(QPen(QColor(255, 255, 255, 28), 1));
    p.drawRoundedRect(card, 28, 28);

    QFont clockFont;
    clockFont.setPointSize(34);
    clockFont.setBold(true);
    p.setFont(clockFont);
    p.setPen(kTextMain);
    p.drawText(QRectF(card.left(), card.top() + 24, card.width(), 68), Qt::AlignHCenter | Qt::AlignVCenter, m_bridge->currentTime());

    QFont monoFont("JetBrains Mono");
    monoFont.setPointSize(11);
    p.setFont(monoFont);
    p.setPen(kTextSub);
    p.drawText(QRectF(card.left(), card.top() + 86, card.width(), 24), Qt::AlignHCenter | Qt::AlignVCenter, m_bridge->currentDate());

    QRectF avatar(card.center().x() - 54, card.top() + 128, 108, 108);
    QLinearGradient avatarGrad(avatar.topLeft(), avatar.bottomRight());
    avatarGrad.setColorAt(0, QColor(200, 182, 255, 76));
    avatarGrad.setColorAt(1, QColor(142, 197, 255, 46));
    p.setBrush(avatarGrad);
    p.setPen(QPen(QColor(255, 255, 255, 30), 1));
    p.drawEllipse(avatar);

    QFont iconFont;
    iconFont.setPointSize(28);
    iconFont.setBold(true);
    p.setFont(iconFont);
    p.setPen(kAccent);
    p.drawText(avatar, Qt::AlignCenter, QStringLiteral("◈"));

    QFont userFont;
    userFont.setPointSize(14);
    userFont.setBold(true);
    p.setFont(userFont);
    p.drawText(QRectF(card.left(), avatar.bottom() + 12, card.width(), 24), Qt::AlignHCenter | Qt::AlignVCenter, m_bridge->username());

    p.setPen(Qt::NoPen);
    p.setBrush(QColor(255, 255, 255, 20));
    p.drawRect(QRectF(card.left() + 34, avatar.bottom() + 46, card.width() - 68, 1));

    QRectF field(card.left() + 100, avatar.bottom() + 64, card.width() - 200, 44);
    p.setBrush(kFieldBg);
    p.setPen(QPen(m_lastFailurePulse > 0 ? kError : kFieldBorder, 1));
    p.drawRoundedRect(field, 22, 22);
    paintTokens(p, field);

    if (m_tokens.empty()) {
        p.setPen(kTextDim);
        p.setFont(monoFont);
        p.drawText(field, Qt::AlignCenter, m_bridge->busy() ? QStringLiteral("Loading...") : QStringLiteral("Enter your password"));
    }

    p.setPen(kTextDim);
    p.drawText(QRectF(card.left(), field.bottom() + 12, card.width(), 20), Qt::AlignHCenter | Qt::AlignVCenter, m_bridge->statusMessage());
    p.drawText(QRectF(card.left(), card.bottom() - 32, card.width(), 18), Qt::AlignHCenter | Qt::AlignVCenter, QStringLiteral("Esc clears • Enter unlocks"));
}

void AuthWindow::paintTokens(QPainter &p, const QRectF &fieldRect) {
    if (m_tokens.empty()) {
        return;
    }

    const qreal tokenSize = 18.0;
    const qreal gap = 8.0;
    const qreal totalWidth = m_tokens.size() * tokenSize + (m_tokens.size() - 1) * gap;
    qreal x = fieldRect.center().x() - totalWidth / 2.0;
    const qreal y = fieldRect.center().y();
    const qint64 now = m_clock.elapsed();

    for (const Token &token : m_tokens) {
        const qreal age = std::min<qreal>(1.0, (now - token.bornMs) / 240.0);
        const qreal scale = 0.1 + age * 0.9;
        const qreal rotation = (1.0 - age) * (token.shapeIndex % 2 == 0 ? -50.0 : 50.0);
        const QPointF center(x + tokenSize / 2.0, y);

        QColor aura = tokenColor(token.colorIndex);
        aura.setAlphaF(0.25 * (1.0 - age));
        p.setPen(Qt::NoPen);
        p.setBrush(aura);
        p.drawEllipse(center, tokenSize * (0.7 + 0.3 * (1.0 - age)), tokenSize * (0.7 + 0.3 * (1.0 - age)));

        p.save();
        p.translate(center);
        p.rotate(rotation);
        paintSingleToken(p, token.shapeIndex, QPointF(0, 0), tokenSize * scale, tokenColor(token.colorIndex));
        p.restore();

        x += tokenSize + gap;
    }
}

void AuthWindow::paintSingleToken(QPainter &p, int shapeIndex, const QPointF &center, qreal size, const QColor &color) {
    const qreal half = size / 2.0;
    const QRectF rect(center.x() - half, center.y() - half, size, size);
    p.setPen(Qt::NoPen);
    p.setBrush(color);

    if (shapeIndex == 0) {
        p.drawRoundedRect(rect, size * 0.22, size * 0.22);
        return;
    }
    if (shapeIndex == 1) {
        p.drawEllipse(rect);
        return;
    }
    QPainterPath path;
    if (shapeIndex == 2) {
        path.moveTo(center.x(), center.y() - half);
        path.lineTo(center.x() + half, center.y() + half * 0.85);
        path.lineTo(center.x() - half, center.y() + half * 0.85);
    } else {
        path.moveTo(center.x(), center.y() - half);
        path.lineTo(center.x() + half, center.y());
        path.lineTo(center.x(), center.y() + half);
        path.lineTo(center.x() - half, center.y());
    }
    path.closeSubpath();
    p.drawPath(path);
}

QColor AuthWindow::tokenColor(int index) const {
    return kShapes[index % 4];
}
