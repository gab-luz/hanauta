import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: root
    width: 1920
    height: 1080

    property color accent: "#7aa2f7"
    property color accent2: "#9ece6a"
    property color bg1: "#0b1020"
    property color bg2: "#111a33"

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: root.bg1 }
            GradientStop { position: 1.0; color: root.bg2 }
        }
    }

    Item {
        id: blobs
        anchors.fill: parent
        opacity: 0.95

        Repeater {
            model: 3
            Rectangle {
                width: Math.max(root.width, root.height) * 0.9
                height: width
                radius: width / 2
                color: index === 0 ? root.accent : (index === 1 ? root.accent2 : "#bb9af7")
                opacity: 0.14
                x: (index === 0 ? -width * 0.25 : (index === 1 ? root.width - width * 0.7 : root.width * 0.1))
                y: (index === 0 ? root.height * 0.15 : (index === 1 ? -height * 0.35 : root.height - height * 0.55))

                transformOrigin: Item.Center
                rotation: 0

                SequentialAnimation on rotation {
                    loops: Animation.Infinite
                    NumberAnimation { from: 0; to: 360; duration: 26000 + index * 6000; easing.type: Easing.InOutSine }
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.35
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 8

        Label {
            text: Qt.formatTime(new Date(), "HH:mm")
            font.pixelSize: 92
            font.weight: Font.DemiBold
            color: "#c0caf5"
            horizontalAlignment: Text.AlignHCenter
            Layout.alignment: Qt.AlignHCenter
        }

        Label {
            text: Qt.formatDate(new Date(), "dddd, dd MMMM yyyy")
            font.pixelSize: 22
            color: "#a9b1d6"
            horizontalAlignment: Text.AlignHCenter
            Layout.alignment: Qt.AlignHCenter
        }

        Rectangle {
            Layout.topMargin: 18
            Layout.alignment: Qt.AlignHCenter
            width: Math.min(root.width * 0.62, 820)
            height: 56
            radius: 18
            color: "#141a2e"
            border.color: "#26304f"
            border.width: 1
            opacity: 0.90

            RowLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 10

                Rectangle {
                    width: 10
                    height: 10
                    radius: 5
                    color: root.accent
                    Layout.alignment: Qt.AlignVCenter
                }

                Label {
                    text: "Locked • Type your password to unlock"
                    font.pixelSize: 16
                    color: "#c0caf5"
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                }
            }
        }
    }
}
