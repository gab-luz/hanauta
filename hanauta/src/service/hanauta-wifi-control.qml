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
                    id: currentNetworkCard
                    Layout.fillWidth: true
                    implicitHeight: currentNetworkContent.implicitHeight + 32
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
                        id: currentNetworkContent
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

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 8
                            rowSpacing: 0

                            Button {
                                text: backend.radioButtonText
                                enabled: !backend.busy
                                onClicked: backend.toggleRadio()
                                Layout.fillWidth: true
                                implicitHeight: 38
                                leftPadding: 16
                                rightPadding: 16
                                topPadding: 9
                                bottomPadding: 9
                                background: Rectangle {
                                    radius: 999
                                    color: parent.hovered ? colors.hoverBg : colors.accentButtonBg
                                    border.width: 1
                                    border.color: colors.accentButtonBorder
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: colors.onPrimaryContainer
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    elide: Text.ElideRight
                                }
                            }

                            Button {
                                text: "Disconnect"
                                enabled: !backend.busy
                                onClicked: backend.disconnectCurrent()
                                Layout.fillWidth: true
                                implicitHeight: 38
                                leftPadding: 14
                                rightPadding: 14
                                topPadding: 9
                                bottomPadding: 9
                                background: Rectangle {
                                    radius: 999
                                    color: parent.hovered ? colors.hoverBg : colors.dangerBg
                                    border.width: 1
                                    border.color: colors.dangerBorder
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: colors.danger
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: selectedNetworkCard
                    Layout.fillWidth: true
                    implicitHeight: selectedNetworkContent.implicitHeight + 28
                    radius: 18
                    color: colors.cardAltBg
                    border.width: 1
                    border.color: colors.runningBorder

                    ColumnLayout {
                        id: selectedNetworkContent
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

                        Button {
                            text: backend.connectButtonText
                            enabled: !backend.busy && backend.selectedSsid.length > 0
                            onClicked: backend.connectSelected(passwordField.text)
                            Layout.fillWidth: true
                            implicitHeight: 36
                            leftPadding: 16
                            rightPadding: 16
                            topPadding: 8
                            bottomPadding: 8
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
                                elide: Text.ElideRight
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

                    ListView {
                        id: networkList
                        anchors.fill: parent
                        anchors.margins: 1
                        clip: true
                        spacing: 8
                        model: backend.networks
                        boundsBehavior: Flickable.StopAtBounds
                        topMargin: 6
                        bottomMargin: 6
                        leftMargin: 6
                        rightMargin: 6

                        ScrollBar.vertical: ScrollBar {
                            policy: ScrollBar.AsNeeded
                        }

                        delegate: Rectangle {
                            id: networkRow
                            required property var modelData
                            property bool hovered: rowArea.containsMouse
                            width: networkList.width - networkList.leftMargin - networkList.rightMargin
                            radius: 16
                            color: hovered ? colors.hoverBg : (modelData.inUse ? Qt.alpha(colors.primary, 0.12) : colors.runningBg)
                            border.width: 1
                            border.color: hovered ? colors.accentButtonBorder : (modelData.inUse ? Qt.alpha(colors.primary, 0.28) : colors.runningBorder)
                            implicitHeight: Math.max(74, networkRowLayout.implicitHeight + 28)

                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            MouseArea {
                                id: rowArea
                                anchors.fill: parent
                                hoverEnabled: true
                                onClicked: backend.selectNetwork(networkRow.modelData.ssid)
                            }

                            RowLayout {
                                id: networkRowLayout
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
                                        text: networkRow.modelData.signalGlyph
                                        color: colors.primary
                                        font.family: backend.materialFontFamily
                                        font.pixelSize: 16
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 3

                                    Text {
                                        Layout.fillWidth: true
                                        text: networkRow.modelData.ssid
                                        color: colors.text
                                        font.family: backend.uiFontFamily
                                        font.pixelSize: 10
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                        maximumLineCount: 1
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: networkRow.modelData.detail
                                        color: colors.textMuted
                                        font.family: backend.uiFontFamily
                                        font.pixelSize: 8
                                        wrapMode: Text.WordWrap
                                    }
                                }

                                Text {
                                    text: networkRow.modelData.trailGlyph
                                    color: networkRow.modelData.inUse ? colors.primary : colors.textMuted
                                    font.family: backend.materialFontFamily
                                    font.pixelSize: 14
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
