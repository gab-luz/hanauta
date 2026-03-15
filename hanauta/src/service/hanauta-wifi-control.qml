import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Effects

Window {
    id: root
    width: 408
    height: 624
    visible: true
    color: "transparent"
    title: "Wi-Fi Control"
    flags: Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint

    property var colors: backend.palette

    function placeWindow() {
        const g = backend.popupGeometry(width, height)
        x = g.x
        y = g.y
    }

    Component.onCompleted: placeWindow()
    onWidthChanged: placeWindow()
    onHeightChanged: placeWindow()

    Rectangle {
        anchors.fill: parent
        color: "transparent"

        Rectangle {
            id: panel
            anchors.fill: parent
            radius: 24
            color: colors.panelBg
            border.width: 1
            border.color: colors.panelBorder

            layer.enabled: true
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: colors.shadow
                shadowVerticalOffset: 14
                shadowBlur: 1
                shadowScale: 1.08
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 16

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: "Network"
                            color: colors.textMuted
                            font.family: backend.uiFontFamily
                            font.pixelSize: 9
                            font.weight: Font.DemiBold
                        }

                        Text {
                            text: "Wi-Fi"
                            color: colors.text
                            font.family: backend.uiFontFamily
                            font.pixelSize: 17
                            font.weight: Font.DemiBold
                        }

                        Text {
                            text: "Secure switching, cleaner status, and quick reconnection."
                            color: colors.textMuted
                            font.family: backend.uiFontFamily
                            font.pixelSize: 9
                            wrapMode: Text.WordWrap
                        }
                    }

                    ToolButton {
                        enabled: !backend.busy
                        text: backend.glyph("refresh")
                        onClicked: backend.refreshNetworks()
                        background: Rectangle {
                            radius: width / 2
                            color: parent.hovered ? colors.hoverBg : colors.cardBg
                            border.width: 1
                            border.color: colors.runningBorder
                        }
                        contentItem: Text {
                            text: parent.text
                            color: colors.icon
                            font.family: backend.materialFontFamily
                            font.pixelSize: 18
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    ToolButton {
                        text: backend.glyph("close")
                        onClicked: backend.closeWindow()
                        background: Rectangle {
                            radius: width / 2
                            color: parent.hovered ? colors.hoverBg : colors.cardBg
                            border.width: 1
                            border.color: colors.runningBorder
                        }
                        contentItem: Text {
                            text: parent.text
                            color: colors.icon
                            font.family: backend.materialFontFamily
                            font.pixelSize: 18
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 20
                    color: colors.cardBg
                    border.width: 1
                    border.color: colors.runningBorder

                    Rectangle {
                        anchors.fill: parent
                        radius: 20
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: colors.heroGlow }
                            GradientStop { position: 1.0; color: "transparent" }
                        }
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 10

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 4

                                Text {
                                    text: "Current network"
                                    color: colors.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 9
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    text: backend.currentConnectionLabel
                                    color: colors.text
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    wrapMode: Text.WordWrap
                                }

                                Text {
                                    text: backend.currentConnectionMeta
                                    color: colors.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 8
                                    wrapMode: Text.WordWrap
                                }
                            }

                            Text {
                                text: backend.currentConnectionIcon
                                color: colors.primary
                                font.family: backend.materialFontFamily
                                font.pixelSize: 22
                                Layout.alignment: Qt.AlignTop
                            }
                        }

                        Button {
                            text: backend.radioButtonText
                            enabled: !backend.busy
                            onClicked: backend.toggleRadio()
                            Layout.alignment: Qt.AlignLeft
                            background: Rectangle {
                                radius: 999
                                color: parent.hovered ? colors.hoverBg : colors.buttonMutedBg
                                border.width: 1
                                border.color: colors.runningBorder
                            }
                            contentItem: Text {
                                text: parent.text
                                color: colors.text
                                font.family: backend.uiFontFamily
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 18
                    color: colors.cardAltBg
                    border.width: 1
                    border.color: colors.runningBorder

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 10

                        Text {
                            text: "Selected access point"
                            color: colors.textMuted
                            font.family: backend.uiFontFamily
                            font.pixelSize: 9
                            font.weight: Font.DemiBold
                        }

                        Text {
                            text: backend.selectedSsid.length > 0 ? backend.selectedSsid : "Select a network"
                            color: colors.text
                            font.family: backend.uiFontFamily
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            text: backend.selectionHint
                            color: colors.textMuted
                            font.family: backend.uiFontFamily
                            font.pixelSize: 8
                            wrapMode: Text.WordWrap
                        }

                        TextField {
                            id: passwordField
                            visible: backend.selectedSecure && !backend.selectedInUse
                            enabled: visible && !backend.busy
                            echoMode: TextInput.Password
                            placeholderText: "Password if required"
                            color: colors.text
                            font.family: backend.uiFontFamily
                            font.pixelSize: 10
                            background: Rectangle {
                                radius: 999
                                color: colors.inputBg
                                border.width: 1
                                border.color: parent.activeFocus ? colors.primary : colors.runningBorder
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Button {
                                text: "Disconnect"
                                enabled: !backend.busy
                                onClicked: backend.disconnectCurrent()
                                background: Rectangle {
                                    radius: 999
                                    color: parent.hovered ? colors.hoverBg : colors.buttonMutedBg
                                    border.width: 1
                                    border.color: colors.runningBorder
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: colors.text
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }

                            Item { Layout.fillWidth: true }

                            Button {
                                text: backend.connectButtonText
                                enabled: !backend.busy && backend.selectedSsid.length > 0
                                onClicked: backend.connectSelected(passwordField.text)
                                background: Rectangle {
                                    radius: 999
                                    color: parent.enabled ? colors.primary : colors.runningBg
                                    border.width: 0
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: parent.enabled ? colors.onPrimary : colors.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: backend.statusText
                    color: colors.textMuted
                    font.family: backend.uiFontFamily
                    font.pixelSize: 9
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 20
                    color: Qt.rgba(0, 0, 0, 0)
                    border.width: 1
                    border.color: colors.runningBorder

                    ScrollView {
                        anchors.fill: parent
                        anchors.margins: 1
                        clip: true
                        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                        ColumnLayout {
                            width: parent.width
                            spacing: 8

                            Repeater {
                                model: backend.networks

                                delegate: Rectangle {
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 6
                                    Layout.rightMargin: 6
                                    Layout.topMargin: 6
                                    radius: 16
                                    color: modelData.inUse ? Qt.alpha(colors.primary, 0.12) : colors.runningBg
                                    border.width: 1
                                    border.color: modelData.inUse ? Qt.alpha(colors.primary, 0.28) : colors.runningBorder
                                    implicitHeight: 74

                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: backend.selectNetwork(modelData.ssid)
                                    }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 12

                                        Rectangle {
                                            Layout.preferredWidth: 38
                                            Layout.preferredHeight: 38
                                            radius: 17
                                            color: colors.runningBg
                                            border.width: 1
                                            border.color: colors.runningBorder

                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData.signalGlyph
                                                color: colors.primary
                                                font.family: backend.materialFontFamily
                                                font.pixelSize: 16
                                            }
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 3

                                            Text {
                                                text: modelData.ssid
                                                color: colors.text
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 10
                                                font.weight: Font.DemiBold
                                            }

                                            Text {
                                                text: modelData.detail
                                                color: colors.textMuted
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 8
                                                wrapMode: Text.WordWrap
                                            }
                                        }

                                        Text {
                                            text: modelData.trailGlyph
                                            color: modelData.inUse ? colors.primary : colors.textMuted
                                            font.family: backend.materialFontFamily
                                            font.pixelSize: 14
                                        }
                                    }
                                }
                            }

                            Item {
                                Layout.fillHeight: true
                                implicitHeight: 6
                            }
                        }
                    }
                }
            }
        }
    }
}
