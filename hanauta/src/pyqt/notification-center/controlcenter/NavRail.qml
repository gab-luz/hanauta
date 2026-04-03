import QtQuick
import QtQuick.Layouts
import "."

Item {
    id: root

    required property var colors
    required property Session session
    required property var backend
    QtObject {
        id: fallbackBackend
        property string materialFontFamily: "Material Icons"
        property string uiFontFamily: "Inter"
        property string monoFontFamily: "JetBrains Mono"
        property string username: "User"
        property string uptime: "0 mins"
        function materialIcon(name) { return name }
        function closeCenter() {}
    }
    property var paneBackend: backend || fallbackBackend

    implicitWidth: 164

    ColumnLayout {
        id: layout
        anchors.fill: parent
        anchors.margins: 18
        spacing: 8

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 60
            radius: 18
            color: root.colors.cardStrongBg
            border.width: 1
            border.color: root.colors.panelBorder

            RowLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 10

                Rectangle {
                    width: 32
                    height: 32
                    radius: 16
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: root.colors.primary }
                        GradientStop { position: 1.0; color: root.colors.tertiary }
                    }

                    Text {
                        anchors.centerIn: parent
                        text: paneBackend.materialIcon("person")
                        font.family: paneBackend.materialFontFamily
                        font.pixelSize: 18
                        color: root.colors.onPrimary
                    }
                }

                ColumnLayout {
                    spacing: 0

                    Text {
                        text: paneBackend.username
                        color: root.colors.text
                        font.family: paneBackend.uiFontFamily
                        font.pixelSize: 12
                        font.weight: Font.Medium
                    }

                    Text {
                        text: "up " + paneBackend.uptime
                        color: root.colors.textMuted
                        font.family: paneBackend.monoFontFamily
                        font.pixelSize: 9
                    }
                }
            }
        }

        Repeater {
            model: PaneRegistry.count

            delegate: Rectangle {
                required property int index
                readonly property var pane: PaneRegistry.getByIndex(index)
                readonly property bool active: root.session.active === pane.label

                Layout.fillWidth: true
                Layout.preferredHeight: 54
                radius: 18
                color: active ? root.colors.primary : "transparent"
                border.width: 1
                border.color: active ? root.colors.primary : "transparent"

                Behavior on color {
                    ColorAnimation { duration: 140 }
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: root.session.active = parent.pane.label
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10

                    Text {
                        text: {
                            if (pane.icon === "router") return "\ue328";
                            if (pane.icon === "settings_bluetooth") return paneBackend.materialIcon("bluetooth");
                            if (pane.icon === "volume_up") return paneBackend.materialIcon("volume_up");
                            if (pane.icon === "palette") return "\ue40a";
                            if (pane.icon === "task_alt") return "\ue2e6";
                            if (pane.icon === "apps") return "\ue5c3";
                            return "\ue871";
                        }
                        font.family: paneBackend.materialFontFamily
                        font.pixelSize: 18
                        color: active ? root.colors.onPrimary : root.colors.icon
                    }

                    Text {
                        text: pane.label.charAt(0).toUpperCase() + pane.label.slice(1)
                        color: active ? root.colors.onPrimary : root.colors.text
                        font.family: paneBackend.uiFontFamily
                        font.pixelSize: 12
                        font.weight: Font.Medium
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            radius: 18
            color: root.colors.cardStrongBg
            border.width: 1
            border.color: root.colors.panelBorder

            MouseArea {
                anchors.fill: parent
                onClicked: paneBackend.closeCenter()
            }

            RowLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 10

                Text {
                    text: paneBackend.materialIcon("power_settings_new")
                    font.family: paneBackend.materialFontFamily
                    font.pixelSize: 18
                    color: root.colors.dangerBg
                }

                Text {
                    text: "Close"
                    color: root.colors.text
                    font.family: paneBackend.uiFontFamily
                    font.pixelSize: 12
                    font.weight: Font.Medium
                }
            }
        }
    }
}
