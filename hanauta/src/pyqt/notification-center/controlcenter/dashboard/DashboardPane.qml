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
        property var phoneInfo: ({})
        property bool homeAssistantVisible: false
        property string homeAssistantStatus: ""
        property var homeAssistantTiles: []
        property var serviceCards: []
        function materialIcon(name) { return name }
        function openSettingsApp(page) {}
        function activateHomeAssistantTile(index) {}
        function launchService(key) {}
    }
    property var paneBackend: backend || fallbackBackend

    function sectionCardHeight(rows) {
        return Math.max(84, rows * 78)
    }

    ScrollView {
        anchors.fill: parent
        anchors.margins: 18
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: parent.availableWidth
            spacing: 12

            Label {
                text: "Dashboard"
                color: root.colors.text
                font.family: paneBackend.uiFontFamily
                font.pixelSize: 22
                font.weight: Font.DemiBold
            }

            Label {
                text: "General system modules and launchers arranged in the Caelestia control-center style."
                color: root.colors.textMuted
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 68
                radius: 22
                color: root.colors.cardStrongBg
                border.width: 1
                border.color: root.colors.panelBorder

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10

                    Image {
                        source: "../../../../assets/kdeconnect.svg"
                        sourceSize.width: 18
                        sourceSize.height: 18
                        fillMode: Image.PreserveAspectFit
                        Layout.preferredWidth: 18
                        Layout.preferredHeight: 18
                    }

                    Label {
                        text: paneBackend.phoneInfo.name || "No devices connected"
                        color: root.colors.text
                        font.family: paneBackend.uiFontFamily
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        Layout.fillWidth: true
                    }

                    Label {
                        text: paneBackend.phoneInfo.status || ""
                        color: root.colors.textMuted
                        font.family: paneBackend.uiFontFamily
                        font.pixelSize: 11
                    }

                    Rectangle {
                        width: 10
                        height: 10
                        radius: 5
                        color: paneBackend.phoneInfo.online ? root.colors.phoneOnline : root.colors.phoneOffline
                    }
                }
            }

            Rectangle {
                visible: paneBackend.homeAssistantVisible
                Layout.fillWidth: true
                Layout.preferredHeight: 124
                radius: 22
                color: root.colors.cardBg
                border.width: 1
                border.color: root.colors.panelBorder

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true

                        Image {
                            source: "../../../../assets/home-assistant-dark.svg"
                            sourceSize.width: 18
                            sourceSize.height: 18
                            fillMode: Image.PreserveAspectFit
                            Layout.preferredWidth: 18
                            Layout.preferredHeight: 18
                        }

                        Label {
                            text: paneBackend.homeAssistantStatus
                            color: root.colors.textMuted
                            font.family: paneBackend.uiFontFamily
                            font.pixelSize: 10
                            Layout.fillWidth: true
                        }

                        Button {
                            text: "Settings"
                            onClicked: paneBackend.openSettingsApp("services")
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Repeater {
                            model: paneBackend.homeAssistantTiles

                            delegate: Rectangle {
                                required property var modelData
                                required property int index
                                Layout.fillWidth: true
                                Layout.preferredHeight: 74
                                radius: 16
                                color: root.colors.cardStrongBg
                                border.width: 1
                                border.color: root.colors.panelBorder

                                MouseArea {
                                    anchors.fill: parent
                                    enabled: parent.modelData.enabled
                                    onClicked: paneBackend.activateHomeAssistantTile(index)
                                }

                                Column {
                                    anchors.centerIn: parent
                                    spacing: 4

                                    Text {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: paneBackend.materialIcon(modelData.icon)
                                        font.family: paneBackend.materialFontFamily
                                        font.pixelSize: 18
                                        color: root.colors.primary
                                    }

                                    Label {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        text: modelData.title
                                        color: root.colors.text
                                        font.family: paneBackend.uiFontFamily
                                        font.pixelSize: 10
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: root.sectionCardHeight(Math.ceil(paneBackend.serviceCards.length / 2))
                radius: 22
                color: root.colors.cardBg
                border.width: 1
                border.color: root.colors.panelBorder

                GridLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    columns: 2
                    columnSpacing: 10
                    rowSpacing: 10

                    Repeater {
                        model: paneBackend.serviceCards

                        delegate: Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredHeight: 70
                            radius: 16
                            color: root.colors.cardStrongBg
                            border.width: 1
                            border.color: root.colors.panelBorder

                            MouseArea {
                                anchors.fill: parent
                                onClicked: paneBackend.launchService(modelData.key)
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 10

                                Text {
                                    text: paneBackend.materialIcon(modelData.icon)
                                    font.family: paneBackend.materialFontFamily
                                    font.pixelSize: 18
                                    color: root.colors.primary
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2

                                    Label {
                                        text: modelData.title
                                        color: root.colors.text
                                        font.family: paneBackend.uiFontFamily
                                        font.pixelSize: 12
                                        font.weight: Font.DemiBold
                                    }

                                    Label {
                                        text: modelData.detail
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
            }
        }
    }
}
