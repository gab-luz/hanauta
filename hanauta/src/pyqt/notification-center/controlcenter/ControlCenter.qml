import QtQuick
import QtQuick.Layouts
import "."

Item {
    id: root

    required property var colors
    required property var backend

    readonly property Session session: Session { }

    Rectangle {
        anchors.fill: parent
        radius: 30
        color: colors.panelBg
        border.width: 1
        border.color: colors.panelBorder
        clip: true

        Rectangle {
            width: 260
            height: 260
            radius: 130
            x: -60
            y: -70
            color: colors.accentSoft
            opacity: 0.24
        }

        Rectangle {
            width: 220
            height: 220
            radius: 110
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.rightMargin: -50
            anchors.bottomMargin: 120
            color: colors.primary
            opacity: 0.08
        }

        RowLayout {
            anchors.fill: parent
            spacing: 0

            Rectangle {
                Layout.fillHeight: true
                Layout.preferredWidth: 184
                color: colors.cardBg
                border.width: 0

                NavRail {
                    anchors.fill: parent
                    colors: root.colors
                    session: root.session
                    backend: root.backend
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "transparent"

                Panes {
                    anchors.fill: parent
                    session: root.session
                    colors: root.colors
                    backend: root.backend
                }
            }
        }
    }
}
