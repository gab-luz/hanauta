import QtQuick
import QtQuick.Layouts
import QtQuick.Window

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

                    Rectangle {
                        id: refreshButton
                        Layout.preferredWidth: 36
                        Layout.preferredHeight: 36
                        radius: width / 2
                        color: refreshArea.containsMouse ? colors.hoverBg : colors.cardBg
                        border.width: 1
                        border.color: colors.runningBorder
                        opacity: backend.busy ? 0.55 : 1.0

                        Text {
                            anchors.centerIn: parent
                            text: backend.glyph("refresh")
                            color: backend.busy ? colors.textMuted : colors.icon
                            font.family: backend.materialFontFamily
                            font.pixelSize: 18
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        MouseArea {
                            id: refreshArea
                            anchors.fill: parent
                            enabled: !backend.busy
                            hoverEnabled: true
                            onClicked: backend.refreshNetworks()
                        }
                    }

                    Rectangle {
                        id: closeButton
                        Layout.preferredWidth: 36
                        Layout.preferredHeight: 36
                        radius: width / 2
                        color: closeArea.containsMouse ? colors.hoverBg : colors.cardBg
                        border.width: 1
                        border.color: colors.runningBorder

                        Text {
                            anchors.centerIn: parent
                            text: backend.glyph("close")
                            color: colors.icon
                            font.family: backend.materialFontFamily
                            font.pixelSize: 18
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        MouseArea {
                            id: closeArea
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: backend.closeWindow()
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

                            Rectangle {
                                id: radioButton
                                Layout.fillWidth: true
                                implicitHeight: 38
                                radius: 999
                                color: radioArea.containsMouse ? colors.hoverBg : colors.accentButtonBg
                                border.width: 1
                                border.color: colors.accentButtonBorder
                                opacity: backend.busy ? 0.55 : 1.0

                                Text {
                                    anchors.centerIn: parent
                                    text: backend.radioButtonText
                                    color: colors.onPrimaryContainer
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    elide: Text.ElideRight
                                }

                                MouseArea {
                                    id: radioArea
                                    anchors.fill: parent
                                    enabled: !backend.busy
                                    hoverEnabled: true
                                    onClicked: backend.toggleRadio()
                                }
                            }

                            Rectangle {
                                id: disconnectButton
                                Layout.fillWidth: true
                                implicitHeight: 38
                                radius: 999
                                color: disconnectArea.containsMouse ? colors.hoverBg : colors.dangerBg
                                border.width: 1
                                border.color: colors.dangerBorder
                                opacity: backend.busy ? 0.55 : 1.0

                                Text {
                                    anchors.centerIn: parent
                                    text: "Disconnect"
                                    color: colors.danger
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    elide: Text.ElideRight
                                }

                                MouseArea {
                                    id: disconnectArea
                                    anchors.fill: parent
                                    enabled: !backend.busy
                                    hoverEnabled: true
                                    onClicked: backend.disconnectCurrent()
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

                        Rectangle {
                            id: passwordField
                            visible: backend.selectedSecure && !backend.selectedInUse
                            enabled: visible && !backend.busy
                            Layout.fillWidth: true
                            implicitHeight: 38
                            radius: 999
                            color: colors.inputBg
                            border.width: 1
                            border.color: passwordInput.activeFocus ? colors.primary : colors.runningBorder

                            TextInput {
                                id: passwordInput
                                anchors.fill: parent
                                anchors.leftMargin: 16
                                anchors.rightMargin: 16
                                verticalAlignment: Text.AlignVCenter
                                echoMode: TextInput.Password
                                color: colors.text
                                font.family: backend.uiFontFamily
                                font.pixelSize: 10
                                enabled: passwordField.enabled
                                clip: true
                            }

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: 16
                                visible: passwordInput.text.length === 0 && !passwordInput.activeFocus
                                text: "Password if required"
                                color: colors.textMuted
                                font.family: backend.uiFontFamily
                                font.pixelSize: 10
                            }

                            MouseArea {
                                anchors.fill: parent
                                enabled: passwordField.enabled
                                onClicked: passwordInput.forceActiveFocus()
                            }
                        }

                        Rectangle {
                            id: connectButton
                            Layout.fillWidth: true
                            implicitHeight: 36
                            radius: 999
                            color: (!backend.busy && backend.selectedSsid.length > 0) ? colors.primary : colors.runningBg

                            Text {
                                anchors.centerIn: parent
                                text: backend.connectButtonText
                                color: (!backend.busy && backend.selectedSsid.length > 0) ? colors.onPrimary : colors.textMuted
                                font.family: backend.uiFontFamily
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                            }

                            MouseArea {
                                anchors.fill: parent
                                enabled: !backend.busy && backend.selectedSsid.length > 0
                                onClicked: backend.connectSelected(passwordInput.text)
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
