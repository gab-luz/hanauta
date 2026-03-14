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
        property string uiFontFamily: "Inter"
        property string materialFontFamily: "Material Icons"
        property string accentName: "orchid"
        function setAccent(key) {}
        function openSettingsApp(page) {}
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
                text: "Appearance"
                color: root.colors.text
                font.family: paneBackend.uiFontFamily
                font.pixelSize: 22
                font.weight: Font.DemiBold
            }

            Label {
                text: "Transplanted from the Caelestia appearance pane concept, backed by Hanauta settings on X11."
                color: root.colors.textMuted
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 116
                radius: 22
                color: root.colors.cardBg
                border.width: 1
                border.color: root.colors.panelBorder

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10

                    Label {
                        text: "Accent"
                        color: root.colors.text
                        font.family: paneBackend.uiFontFamily
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }

                    RowLayout {
                        spacing: 10

                        Repeater {
                            model: ["orchid", "mint", "sunset"]

                            delegate: Rectangle {
                                required property string modelData
                                width: 84
                                height: 42
                                radius: 16
                                color: paneBackend.accentName === modelData ? root.colors.primary : root.colors.cardStrongBg
                                border.width: 1
                                border.color: paneBackend.accentName === modelData ? root.colors.primary : root.colors.panelBorder

                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: paneBackend.setAccent(modelData)
                                }

                                Label {
                                    anchors.centerIn: parent
                                    text: modelData.charAt(0).toUpperCase() + modelData.slice(1)
                                    color: paneBackend.accentName === modelData ? root.colors.onPrimary : root.colors.text
                                    font.family: paneBackend.uiFontFamily
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 90
                radius: 22
                color: root.colors.cardBg
                border.width: 1
                border.color: root.colors.panelBorder

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12

                    Text {
                        text: "\ue8b8"
                        font.family: paneBackend.materialFontFamily
                        font.pixelSize: 18
                        color: root.colors.primary
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Label {
                            text: "Open full appearance settings"
                            color: root.colors.text
                            font.family: paneBackend.uiFontFamily
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }
                        Label {
                            text: "Wallpaper, Matugen, display layout, and transparency controls stay in Hanauta Settings."
                            color: root.colors.textMuted
                            font.family: paneBackend.uiFontFamily
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                        }
                    }

                    Button {
                        text: "Open"
                        onClicked: paneBackend.openSettingsApp("appearance")
                    }
                }
            }
        }
    }
}
