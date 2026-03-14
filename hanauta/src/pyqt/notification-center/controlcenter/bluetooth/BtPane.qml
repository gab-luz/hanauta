import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    required property var colors
    property var session
    required property var backend
    QtObject {
        id: fallbackBackend
        property string materialFontFamily: "Material Icons"
        property string uiFontFamily: "Inter"
        property var quickSettings: []
        function materialIcon(name) { return name }
        function toggleQuickSetting(key) {}
    }
    property var paneBackend: backend || fallbackBackend

    ScrollView {
        anchors.fill: parent
        anchors.margins: 18
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: parent.availableWidth
            spacing: 12

            Label {
                text: "Bluetooth"
                color: root.colors.text
                font.family: paneBackend.uiFontFamily
                font.pixelSize: 22
                font.weight: Font.DemiBold
            }

            Label {
                text: "X11-compatible alternative to the Caelestia Bluetooth pane."
                color: root.colors.textMuted
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Repeater {
                model: paneBackend.quickSettings

                delegate: Rectangle {
                    required property var modelData
                    visible: modelData.key === "bluetooth"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 90
                    radius: 22
                    color: modelData.active ? root.colors.primary : root.colors.cardBg
                    border.width: 1
                    border.color: modelData.active ? root.colors.primary : root.colors.panelBorder

                    MouseArea {
                        anchors.fill: parent
                        onClicked: paneBackend.toggleQuickSetting("bluetooth")
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: paneBackend.materialIcon("bluetooth")
                            font.family: paneBackend.materialFontFamily
                            font.pixelSize: 22
                            color: modelData.active ? root.colors.onPrimary : root.colors.primary
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            Label {
                                text: "Bluetooth radio"
                                color: modelData.active ? root.colors.onPrimary : root.colors.text
                                font.family: paneBackend.uiFontFamily
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                            }
                            Label {
                                text: modelData.subtitle
                                color: modelData.active ? root.colors.onPrimary : root.colors.textMuted
                                font.family: paneBackend.uiFontFamily
                                font.pixelSize: 11
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 86
                radius: 22
                color: root.colors.cardBg
                border.width: 1
                border.color: root.colors.panelBorder

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 4

                    Label {
                        text: "Details"
                        color: root.colors.text
                        font.family: paneBackend.uiFontFamily
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                    Label {
                        text: "Caelestia shows device lists here through Quickshell Bluetooth APIs. On X11, Hanauta keeps the same pane placement and card sizing, but uses the radio toggle until a native device model is added."
                        color: root.colors.textMuted
                        font.family: paneBackend.uiFontFamily
                        font.pixelSize: 10
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }
        }
    }
}
