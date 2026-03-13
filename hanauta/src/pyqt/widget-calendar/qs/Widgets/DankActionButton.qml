import QtQuick
import qs.Common
import qs.Widgets

Rectangle {
    id: root

    property string iconName: ""
    property int iconSize: 16
    property color iconColor: Theme.surfaceText
    property int buttonSize: 28
    property bool enabled: true

    signal clicked()

    width: buttonSize
    height: buttonSize
    radius: Theme.cornerRadius
    color: mouse.containsMouse && enabled ? Theme.withAlpha(Theme.primary, 0.12) : "transparent"
    opacity: enabled ? 1.0 : 0.5

    DankIcon {
        anchors.centerIn: parent
        name: root.iconName
        size: root.iconSize
        color: root.iconColor
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        enabled: root.enabled
        hoverEnabled: true
        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: root.clicked()
    }
}
