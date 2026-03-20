import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Window {
    id: root
    width: 438
    height: 736
    visible: true
    color: "transparent"
    title: "Hanauta Home Assistant"
    flags: Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint

    function glyph(name) {
        return backend.materialIcon(name)
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"

        Rectangle {
            id: panel
            anchors.fill: parent
            anchors.margins: 12
            radius: 28
            gradient: Gradient {
                GradientStop { position: 0.0; color: themeModel.panelStart }
                GradientStop { position: 1.0; color: themeModel.panelEnd }
            }
            border.width: 1
            border.color: themeModel.border
            clip: true

            Rectangle {
                width: 220
                height: 220
                radius: 110
                x: -44
                y: -66
                color: themeModel.heroStart
                opacity: 0.28
            }

            Rectangle {
                width: 170
                height: 170
                radius: 85
                anchors.right: parent.right
                anchors.rightMargin: -42
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 120
                color: themeModel.primary
                opacity: 0.08
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Rectangle {
                        width: 42
                        height: 42
                        radius: 21
                        color: themeModel.active
                        border.width: 1
                        border.color: themeModel.activeBorder

                        Text {
                            anchors.centerIn: parent
                            text: glyph("home")
                            font.family: backend.materialFontFamily
                            font.pixelSize: 20
                            color: themeModel.primary
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: "HOME ASSISTANT"
                            color: themeModel.primary
                            font.family: backend.uiFontFamily
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                        }

                        Text {
                            text: backend.statusHeadline
                            color: themeModel.text
                            font.family: backend.displayFontFamily
                            font.pixelSize: 18
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }

                        Text {
                            text: backend.statusHint
                            color: themeModel.textMuted
                            font.family: backend.uiFontFamily
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    RoundButton {
                        text: glyph("settings")
                        font.family: backend.materialFontFamily
                        font.pixelSize: 18
                        onClicked: backend.openSettings()
                        background: Rectangle {
                            radius: width / 2
                            color: parent.hovered ? themeModel.active : themeModel.card
                            border.width: 1
                            border.color: themeModel.border
                        }
                    }

                    RoundButton {
                        text: glyph("refresh")
                        font.family: backend.materialFontFamily
                        font.pixelSize: 18
                        enabled: !backend.busy
                        onClicked: backend.refresh()
                        background: Rectangle {
                            radius: width / 2
                            color: parent.hovered ? themeModel.active : themeModel.card
                            border.width: 1
                            border.color: themeModel.border
                        }
                    }

                    RoundButton {
                        text: glyph("close")
                        font.family: backend.materialFontFamily
                        font.pixelSize: 18
                        onClicked: backend.closeWindow()
                        background: Rectangle {
                            radius: width / 2
                            color: parent.hovered ? Qt.rgba(1, 0.35, 0.35, 0.18) : themeModel.card
                            border.width: 1
                            border.color: themeModel.border
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 22
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: themeModel.heroStart }
                        GradientStop { position: 1.0; color: themeModel.heroEnd }
                    }
                    border.width: 1
                    border.color: themeModel.activeBorder
                    implicitHeight: heroColumn.implicitHeight + 26

                    ColumnLayout {
                        id: heroColumn
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 10

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Rectangle {
                                width: 10
                                height: 10
                                radius: 5
                                color: backend.available ? themeModel.good : themeModel.danger
                            }

                            Text {
                                text: backend.available ? "Connected" : "Unavailable"
                                color: themeModel.text
                                font.family: backend.uiFontFamily
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                            }

                            Item { Layout.fillWidth: true }

                            Rectangle {
                                radius: 999
                                color: themeModel.cardStrong
                                border.width: 1
                                border.color: themeModel.border
                                implicitHeight: 28
                                implicitWidth: latencyText.implicitWidth + 22

                                Text {
                                    id: latencyText
                                    anchors.centerIn: parent
                                    text: backend.latencyMs >= 0 ? backend.latencyMs + " ms" : "No ping"
                                    color: themeModel.text
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                }
                            }
                        }

                        Text {
                            text: backend.pinnedEntities.length > 0
                                ? backend.pinnedEntities.length + " pinned shortcuts ready"
                                : "Pin your most-used entities so they stay at the top like the reference widget."
                            color: themeModel.textMuted
                            font.family: backend.uiFontFamily
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 48
                    radius: 18
                    color: themeModel.card
                    border.width: 1
                    border.color: themeModel.border

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 10

                        Text {
                            text: glyph("search")
                            font.family: backend.materialFontFamily
                            font.pixelSize: 18
                            color: themeModel.primary
                        }

                        TextField {
                            id: searchField
                            Layout.fillWidth: true
                            text: backend.searchQuery
                            placeholderText: "Search entities, rooms, or IDs"
                            color: themeModel.text
                            placeholderTextColor: themeModel.textMuted
                            font.family: backend.uiFontFamily
                            font.pixelSize: 12
                            background: Rectangle { color: "transparent" }
                            onTextChanged: backend.setSearchQuery(text)
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    visible: backend.pinnedEntities.length > 0
                    radius: 20
                    color: themeModel.card
                    border.width: 1
                    border.color: themeModel.border
                    implicitHeight: pinnedFlow.implicitHeight + 28

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 10

                        Text {
                            text: "Pinned shortcuts"
                            color: themeModel.text
                            font.family: backend.uiFontFamily
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }

                        Flow {
                            id: pinnedFlow
                            Layout.fillWidth: true
                            width: parent.width
                            spacing: 8

                            Repeater {
                                model: backend.pinnedEntities

                                delegate: Rectangle {
                                    required property var modelData
                                    width: (pinnedFlow.width - 8) / 2
                                    height: 74
                                    radius: 18
                                    color: themeModel.cardStrong
                                    border.width: 1
                                    border.color: themeModel.border

                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: backend.activateEntity(modelData.entityId)
                                    }

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 4

                                        RowLayout {
                                            Layout.fillWidth: true

                                            Text {
                                                text: modelData.iconGlyph
                                                font.family: backend.materialFontFamily
                                                font.pixelSize: 18
                                                color: themeModel.primary
                                            }

                                            Item { Layout.fillWidth: true }

                                            Text {
                                                text: glyph("push_pin")
                                                font.family: backend.materialFontFamily
                                                font.pixelSize: 15
                                                color: themeModel.textMuted
                                            }
                                        }

                                        Text {
                                            text: modelData.friendlyName
                                            color: themeModel.text
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 11
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }

                                        Text {
                                            text: modelData.state
                                            color: themeModel.textMuted
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 10
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                    Column {
                        width: parent.width
                        spacing: 8

                        Repeater {
                            model: backend.entities

                            delegate: Rectangle {
                                id: entityCard
                                required property var modelData
                                property bool expanded: false
                                width: parent.width
                                radius: 20
                                color: themeModel.card
                                border.width: 1
                                border.color: expanded ? themeModel.activeBorder : themeModel.border
                                implicitHeight: cardColumn.implicitHeight + 24

                                ColumnLayout {
                                    id: cardColumn
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 10

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 10

                                        Rectangle {
                                            width: 38
                                            height: 38
                                            radius: 19
                                            color: modelData.stateTone === "active" ? themeModel.active : themeModel.cardStrong
                                            border.width: 1
                                            border.color: modelData.stateTone === "active" ? themeModel.activeBorder : themeModel.border

                                            Text {
                                                anchors.centerIn: parent
                                                text: modelData.iconGlyph
                                                font.family: backend.materialFontFamily
                                                font.pixelSize: 18
                                                color: themeModel.primary
                                            }
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 2

                                            Text {
                                                text: modelData.friendlyName
                                                color: themeModel.text
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 12
                                                font.weight: Font.DemiBold
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }

                                            Text {
                                                text: modelData.secondary
                                                color: themeModel.textMuted
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 10
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }
                                        }

                                        Rectangle {
                                            radius: 999
                                            color: modelData.stateTone === "active" ? themeModel.active : themeModel.cardStrong
                                            border.width: 1
                                            border.color: modelData.stateTone === "active" ? themeModel.activeBorder : themeModel.border
                                            implicitWidth: stateLabel.implicitWidth + 20
                                            implicitHeight: 28

                                            Text {
                                                id: stateLabel
                                                anchors.centerIn: parent
                                                text: modelData.state
                                                color: themeModel.text
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 10
                                            }
                                        }
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8

                                        Button {
                                            visible: modelData.canToggle
                                            text: modelData.actionLabel
                                            onClicked: backend.activateEntity(modelData.entityId)
                                        }

                                        Button {
                                            text: modelData.isPinned ? "Unpin" : "Pin"
                                            onClicked: backend.togglePinned(modelData.entityId)
                                        }

                                        Item { Layout.fillWidth: true }

                                        Button {
                                            text: expanded ? "Less" : "More"
                                            onClicked: entityCard.expanded = !entityCard.expanded
                                        }
                                    }

                                    ColumnLayout {
                                        visible: expanded
                                        Layout.fillWidth: true
                                        spacing: 6

                                        Rectangle {
                                            Layout.fillWidth: true
                                            radius: 14
                                            color: themeModel.cardStrong
                                            border.width: 1
                                            border.color: themeModel.border
                                            implicitHeight: detailsText.implicitHeight + 18

                                            Text {
                                                id: detailsText
                                                anchors.fill: parent
                                                anchors.margins: 10
                                                text: modelData.details.length > 0 ? modelData.details : modelData.entityId
                                                color: themeModel.textMuted
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 10
                                                wrapMode: Text.WordWrap
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
    }

    Shortcut {
        sequence: "Esc"
        onActivated: backend.closeWindow()
    }

    Shortcut {
        sequence: "Ctrl+R"
        onActivated: backend.refresh()
    }
}
