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
        function launchService(key) {}
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
                text: "Network"
                color: root.colors.text
                font.family: paneBackend.uiFontFamily
                font.pixelSize: 22
                font.weight: Font.DemiBold
            }

            Label {
                text: "Wireless, VPN, and radio controls arranged like the Caelestia networking pane."
                color: root.colors.textMuted
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 10
                rowSpacing: 10

                Repeater {
                    model: paneBackend.quickSettings

                    delegate: Rectangle {
                        required property var modelData
                        readonly property bool keepHere: modelData.key === "wifi" || modelData.key === "airplane" || modelData.key === "dnd"
                        visible: keepHere
                        Layout.fillWidth: true
                        Layout.preferredHeight: 82
                        radius: 18
                        color: modelData.active ? root.colors.primary : root.colors.cardBg
                        border.width: 1
                        border.color: modelData.active ? root.colors.primary : root.colors.panelBorder

                        MouseArea {
                            anchors.fill: parent
                            onClicked: paneBackend.toggleQuickSetting(modelData.key)
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 10

                            Text {
                                text: paneBackend.materialIcon(modelData.icon)
                                font.family: paneBackend.materialFontFamily
                                font.pixelSize: 20
                                color: modelData.active ? root.colors.onPrimary : root.colors.icon
                            }

                            ColumnLayout {
                                Layout.fillWidth: true

                                Label {
                                    text: modelData.title
                                    color: modelData.active ? root.colors.onPrimary : root.colors.text
                                    font.family: paneBackend.uiFontFamily
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                }

                                Label {
                                    text: modelData.subtitle
                                    color: modelData.active ? root.colors.onPrimary : root.colors.textMuted
                                    font.family: paneBackend.uiFontFamily
                                    font.pixelSize: 10
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 84
                radius: 22
                color: root.colors.cardBg
                border.width: 1
                border.color: root.colors.panelBorder

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10

                    Text {
                        text: paneBackend.materialIcon("lock")
                        font.family: paneBackend.materialFontFamily
                        font.pixelSize: 18
                        color: root.colors.primary
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Label {
                            text: "VPN"
                            color: root.colors.text
                            font.family: paneBackend.uiFontFamily
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                        Label {
                            text: "Open the Hanauta VPN control widget."
                            color: root.colors.textMuted
                            font.family: paneBackend.uiFontFamily
                            font.pixelSize: 10
                        }
                    }

                    Button {
                        text: "Open"
                        onClicked: paneBackend.launchService("vpn_control")
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 84
                radius: 22
                color: root.colors.cardBg
                border.width: 1
                border.color: root.colors.panelBorder

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10

                    Text {
                        text: "\ue1a7"
                        font.family: paneBackend.materialFontFamily
                        font.pixelSize: 18
                        color: root.colors.primary
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Label {
                            text: "Bluetooth"
                            color: root.colors.text
                            font.family: paneBackend.uiFontFamily
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                        Label {
                            text: "Switch to the Bluetooth pane for dedicated controls."
                            color: root.colors.textMuted
                            font.family: paneBackend.uiFontFamily
                            font.pixelSize: 10
                        }
                    }

                    Button {
                        text: "Go"
                        onClicked: root.session.active = "bluetooth"
                    }
                }
            }
        }
    }
}
