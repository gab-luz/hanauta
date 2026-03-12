import QtQuick
import "theme.js" as Theme

Item {
    id: root

    required property var bridge
    property bool saverMode: false

    implicitWidth: Theme.cardWidth
    implicitHeight: Theme.cardHeight

    Rectangle {
        id: card
        anchors.fill: parent
        radius: Theme.cardRadius
        color: Qt.rgba(0.11, 0.08, 0.15, 0.9)
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.12)
        scale: 0.94
        opacity: 0
        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 10
            anchors.leftMargin: 10
            anchors.rightMargin: -10
            anchors.bottomMargin: -14
            z: -1
            radius: Theme.cardRadius
            color: Qt.rgba(0, 0, 0, 0.22)
        }

        Item {
            anchors.fill: parent
            anchors.margins: 34

            Item {
                id: clockRow
                anchors.top: parent.top
                anchors.horizontalCenter: parent.horizontalCenter
                width: hourText.width + colonText.width + minuteText.width + 20
                height: 72

                Text {
                    id: hourText
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: bridge.currentTime.slice(0, 2)
                    color: Theme.textMain
                    font.pixelSize: 64
                    font.bold: true
                }

                Text {
                    id: colonText
                    anchors.left: hourText.right
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: ":"
                    color: Theme.accent
                    font.pixelSize: 64
                    font.bold: true
                }

                Text {
                    id: minuteText
                    anchors.left: colonText.right
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: bridge.currentTime.slice(3, 5)
                    color: Theme.textMain
                    font.pixelSize: 64
                    font.bold: true
                }
            }

            Text {
                id: dateText
                anchors.top: clockRow.bottom
                anchors.topMargin: 4
                anchors.horizontalCenter: parent.horizontalCenter
                text: bridge.currentDate
                color: Theme.textSub
                font.pixelSize: 18
                font.family: "JetBrains Mono"
            }

            Item {
                id: avatarWrap
                anchors.top: dateText.bottom
                anchors.topMargin: 24
                anchors.horizontalCenter: parent.horizontalCenter
                width: 108
                height: 108

                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    gradient: Gradient {
                        GradientStop { position: 0; color: Qt.rgba(0.78, 0.71, 1.0, 0.3) }
                        GradientStop { position: 1; color: Qt.rgba(0.56, 0.77, 1.0, 0.18) }
                    }
                    border.width: 1
                    border.color: Qt.rgba(1, 1, 1, 0.12)
                }

                Text {
                    anchors.centerIn: parent
                    text: "◈"
                    color: Theme.accent
                    font.pixelSize: 42
                    font.bold: true
                }
            }

            Text {
                id: usernameText
                anchors.top: avatarWrap.bottom
                anchors.topMargin: 14
                anchors.horizontalCenter: parent.horizontalCenter
                text: bridge.username
                color: Theme.accent
                font.pixelSize: 22
                font.bold: true
            }

            Rectangle {
                id: divider
                anchors.top: usernameText.bottom
                anchors.topMargin: 10
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: Qt.rgba(1, 1, 1, 0.08)
            }

            InputField {
                id: inputField
                anchors.top: divider.bottom
                anchors.topMargin: 18
                anchors.horizontalCenter: parent.horizontalCenter
                bufferText: saverMode ? "" : bridge.buffer
                failurePulse: saverMode ? 0 : bridge.failurePulse
                busy: saverMode ? false : bridge.busy
            }

            Text {
                id: statusText
                anchors.top: inputField.bottom
                anchors.topMargin: 10
                anchors.horizontalCenter: parent.horizontalCenter
                text: saverMode ? "xsecurelock saver_hanauta" : bridge.statusMessage
                color: Theme.textDim
                font.pixelSize: 14
                font.family: "JetBrains Mono"
            }

            Text {
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                text: saverMode ? "Press any key to open auth" : "Esc clears • Enter unlocks"
                color: Qt.rgba(1, 1, 1, 0.55)
                font.pixelSize: 13
                font.family: "JetBrains Mono"
            }
        }
    }

    ParallelAnimation {
        running: true

        NumberAnimation {
            target: card
            property: "scale"
            from: 0.94
            to: 1.0
            duration: 260
            easing.type: Easing.OutCubic
        }
        NumberAnimation {
            target: card
            property: "opacity"
            from: 0
            to: 1
            duration: 220
            easing.type: Easing.OutCubic
        }
    }
}
