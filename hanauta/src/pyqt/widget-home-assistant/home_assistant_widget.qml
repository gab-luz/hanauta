import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Effects

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

    component IconVisual: Item {
        id: iconRoot
        property string glyphText: ""
        property string iconSource: ""
        property color tintColor: themeModel.iconTint
        property int iconSize: 20

        implicitWidth: iconSize
        implicitHeight: iconSize
        width: implicitWidth
        height: implicitHeight

        Text {
            anchors.centerIn: parent
            visible: iconRoot.iconSource === ""
            text: iconRoot.glyphText
            font.family: backend.materialFontFamily
            font.pixelSize: iconRoot.iconSize
            color: iconRoot.tintColor
            renderType: Text.NativeRendering
        }

        Item {
            anchors.centerIn: parent
            width: iconRoot.iconSize
            height: iconRoot.iconSize
            visible: iconRoot.iconSource !== ""
            layer.enabled: true
            layer.smooth: true

            layer.effect: MultiEffect {
                colorization: 1.0
                colorizationColor: iconRoot.tintColor
            }

            Image {
                anchors.fill: parent
                anchors.margins: 1
                source: iconRoot.iconSource
                fillMode: Image.PreserveAspectFit
                sourceSize.width: iconRoot.iconSize
                sourceSize.height: iconRoot.iconSize
                asynchronous: true
                cache: true
                smooth: true
                mipmap: true
            }
        }
    }

    component CircleIconButton: Button {
        id: circleControl
        property string iconText: ""
        property color iconColor: themeModel.iconTint
        property color baseColor: themeModel.card
        property color hoverColor: themeModel.hover
        property color pressColor: themeModel.pressed
        property color strokeColor: themeModel.border

        implicitWidth: 38
        implicitHeight: 38
        hoverEnabled: true
        padding: 0

        background: Rectangle {
            radius: width / 2
            color: !circleControl.enabled
                   ? themeModel.card
                   : circleControl.pressed
                        ? circleControl.pressColor
                        : circleControl.hovered
                            ? circleControl.hoverColor
                            : circleControl.baseColor
            border.width: 1
            border.color: circleControl.strokeColor
            opacity: circleControl.enabled ? 1.0 : 0.55
        }

        contentItem: Text {
            text: circleControl.iconText
            font.family: backend.materialFontFamily
            font.pixelSize: 18
            color: circleControl.iconColor
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            renderType: Text.NativeRendering
        }
    }

    component PillButton: Button {
        id: pillControl
        property color fillColor: themeModel.cardStrong
        property color hoverColor: themeModel.hover
        property color pressColor: themeModel.pressed
        property color strokeColor: themeModel.border
        property color labelColor: themeModel.text
        property string labelText: text
        property string labelFamily: backend.uiFontFamily
        property int labelSize: 11
        property int labelWeight: Font.DemiBold

        implicitHeight: 32
        implicitWidth: Math.max(76, contentItem.implicitWidth + leftPadding + rightPadding)
        leftPadding: 12
        rightPadding: 12
        topPadding: 0
        bottomPadding: 0
        hoverEnabled: true

        background: Rectangle {
            radius: 12
            color: !pillControl.enabled
                   ? themeModel.cardStrong
                   : pillControl.pressed
                        ? pillControl.pressColor
                        : pillControl.hovered
                            ? pillControl.hoverColor
                            : pillControl.fillColor
            border.width: 1
            border.color: pillControl.strokeColor
            opacity: pillControl.enabled ? 1.0 : 0.55
        }

        contentItem: Text {
            text: pillControl.labelText
            color: pillControl.labelColor
            font.family: pillControl.labelFamily
            font.pixelSize: pillControl.labelSize
            font.weight: pillControl.labelWeight
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            renderType: Text.NativeRendering
        }
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
                opacity: 0.24
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
                opacity: 0.05
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

                        IconVisual {
                            anchors.centerIn: parent
                            glyphText: glyph("home")
                            iconSize: 20
                            tintColor: themeModel.iconTint
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
                            renderType: Text.NativeRendering
                        }

                        Text {
                            text: backend.statusHeadline
                            color: themeModel.text
                            font.family: backend.displayFontFamily
                            font.pixelSize: 18
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                            renderType: Text.NativeRendering
                        }

                        Text {
                            text: backend.statusHint
                            color: themeModel.textMuted
                            font.family: backend.uiFontFamily
                            font.pixelSize: 11
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                            renderType: Text.NativeRendering
                        }
                    }

                    CircleIconButton {
                        iconText: glyph("settings")
                        onClicked: backend.openSettings()
                    }

                    CircleIconButton {
                        iconText: glyph("refresh")
                        enabled: !backend.busy
                        onClicked: backend.refresh()
                    }

                    CircleIconButton {
                        iconText: glyph("close")
                        iconColor: themeModel.text
                        hoverColor: Qt.rgba(1.0, 0.35, 0.35, 0.16)
                        pressColor: Qt.rgba(1.0, 0.35, 0.35, 0.24)
                        onClicked: backend.closeWindow()
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
                                renderType: Text.NativeRendering
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
                                    renderType: Text.NativeRendering
                                }
                            }
                        }

                        Text {
                            text: backend.pinnedEntities.length > 0
                                  ? backend.pinnedEntities.length + " pinned shortcuts ready"
                                  : "Pin your most-used entities so they stay at the top."
                            color: themeModel.textMuted
                            font.family: backend.uiFontFamily
                            font.pixelSize: 11
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                            renderType: Text.NativeRendering
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 48
                    radius: 18
                    color: themeModel.field
                    border.width: 1
                    border.color: themeModel.border

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 10

                        IconVisual {
                            glyphText: glyph("search")
                            iconSize: 18
                            tintColor: themeModel.iconTint
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
                            selectByMouse: true
                            leftPadding: 0
                            rightPadding: 0
                            topPadding: 0
                            bottomPadding: 0
                            background: Item {}
                            onTextChanged: backend.setSearchQuery(text)
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: backend.entities.length + " entity cards"
                    color: themeModel.textMuted
                    font.family: backend.uiFontFamily
                    font.pixelSize: 10
                    renderType: Text.NativeRendering
                }

                Rectangle {
                    id: shortcutsSection
                    Layout.fillWidth: true
                    Layout.preferredHeight: visible ? implicitHeight : 0
                    visible: backend.pinnedEntities.length > 0
                    radius: 20
                    color: themeModel.card
                    border.width: 1
                    border.color: themeModel.border
                    implicitHeight: shortcutsColumn.implicitHeight + 28

                    ColumnLayout {
                        id: shortcutsColumn
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 10

                        Text {
                            text: "Pinned shortcuts"
                            color: themeModel.text
                            font.family: backend.uiFontFamily
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            renderType: Text.NativeRendering
                        }

                        Flow {
                            id: pinnedFlow
                            Layout.fillWidth: true
                            width: shortcutsSection.width - 28
                            spacing: 8

                            Repeater {
                                model: backend.pinnedEntities

                                delegate: Rectangle {
                                    required property var modelData
                                    width: Math.max(120, (pinnedFlow.width - pinnedFlow.spacing) / 2)
                                    height: 78
                                    radius: 18
                                    color: themeModel.cardStrong
                                    border.width: 1
                                    border.color: themeModel.border

                                    MouseArea {
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        onClicked: backend.activateEntity(modelData.entityId)
                                    }

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 4

                                        RowLayout {
                                            Layout.fillWidth: true

                                            IconVisual {
                                                glyphText: modelData.iconGlyph
                                                iconSource: modelData.iconSource
                                                iconSize: 18
                                                tintColor: themeModel.iconTint
                                            }

                                            Item { Layout.fillWidth: true }

                                            IconVisual {
                                                glyphText: glyph("push_pin")
                                                iconSize: 15
                                                tintColor: themeModel.iconMuted
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
                                            renderType: Text.NativeRendering
                                        }

                                        Text {
                                            text: modelData.state
                                            color: themeModel.textMuted
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 10
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                            renderType: Text.NativeRendering
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                ScrollView {
                    id: entitiesScroll
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    contentWidth: availableWidth
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    background: Item {}

                    Column {
                        id: entitiesColumn
                        width: entitiesScroll.availableWidth
                        spacing: 8

                        Rectangle {
                            visible: backend.entities.length === 0
                            width: parent.width
                            radius: 20
                            color: themeModel.card
                            border.width: 1
                            border.color: themeModel.border
                            implicitHeight: emptyColumn.implicitHeight + 28

                            ColumnLayout {
                                id: emptyColumn
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 8

                                Text {
                                    text: backend.available ? "No entities match your search." : "No Home Assistant entities to show yet."
                                    color: themeModel.text
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                    renderType: Text.NativeRendering
                                }

                                Text {
                                    text: backend.available
                                          ? "Try another search term or clear the field."
                                          : "Check your Home Assistant URL and token in Settings."
                                    color: themeModel.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 10
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                    renderType: Text.NativeRendering
                                }
                            }
                        }

                        Repeater {
                            model: backend.entities

                            delegate: Rectangle {
                                id: entityCard
                                required property var modelData
                                property bool expanded: false

                                width: entitiesColumn.width
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
                                            width: 40
                                            height: 40
                                            radius: 20
                                            color: modelData.stateTone === "active" ? themeModel.active : themeModel.cardStrong
                                            border.width: 1
                                            border.color: modelData.stateTone === "active"
                                                          ? themeModel.activeBorder
                                                          : themeModel.border

                                            IconVisual {
                                                anchors.centerIn: parent
                                                glyphText: modelData.iconGlyph
                                                iconSource: modelData.iconSource
                                                iconSize: 18
                                                tintColor: themeModel.iconTint
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
                                                renderType: Text.NativeRendering
                                            }

                                            Text {
                                                text: modelData.secondary
                                                color: themeModel.textMuted
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 10
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                                renderType: Text.NativeRendering
                                            }

                                            Text {
                                                text: modelData.entityId
                                                color: themeModel.textMuted
                                                opacity: 0.85
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 9
                                                elide: Text.ElideMiddle
                                                Layout.fillWidth: true
                                                renderType: Text.NativeRendering
                                            }
                                        }

                                        Rectangle {
                                            radius: 999
                                            color: modelData.stateTone === "active" ? themeModel.active : themeModel.cardStrong
                                            border.width: 1
                                            border.color: modelData.stateTone === "active"
                                                          ? themeModel.activeBorder
                                                          : themeModel.border
                                            implicitWidth: stateLabel.implicitWidth + 20
                                            implicitHeight: 28

                                            Text {
                                                id: stateLabel
                                                anchors.centerIn: parent
                                                text: modelData.state
                                                color: themeModel.text
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 10
                                                renderType: Text.NativeRendering
                                            }
                                        }
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8

                                        Rectangle {
                                            radius: 999
                                            color: themeModel.cardStrong
                                            border.width: 1
                                            border.color: themeModel.border
                                            implicitWidth: domainText.implicitWidth + 18
                                            implicitHeight: 24

                                            Text {
                                                id: domainText
                                                anchors.centerIn: parent
                                                text: modelData.domainLabel
                                                color: themeModel.textMuted
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 9
                                                font.weight: Font.DemiBold
                                                renderType: Text.NativeRendering
                                            }
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            text: modelData.updatedText
                                            color: themeModel.textMuted
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 9
                                            elide: Text.ElideRight
                                            renderType: Text.NativeRendering
                                        }
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8

                                        PillButton {
                                            id: actionButton
                                            visible: modelData.canToggle
                                            enabled: modelData.canToggle
                                            labelText: modelData.actionLabel
                                            strokeColor: themeModel.activeBorder
                                            onClicked: backend.activateEntity(modelData.entityId)
                                        }

                                        PillButton {
                                            id: pinButton
                                            labelText: modelData.isPinned ? glyph("push_pin") : glyph("push_pin_outline")
                                            labelFamily: backend.materialFontFamily
                                            labelSize: 18
                                            strokeColor: modelData.isPinned ? themeModel.activeBorder : themeModel.border
                                            fillColor: modelData.isPinned ? themeModel.active : themeModel.cardStrong
                                            onClicked: backend.togglePinned(modelData.entityId)
                                        }

                                        Item { Layout.fillWidth: true }

                                        PillButton {
                                            id: expandButton
                                            labelText: expanded ? "Less" : "More"
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
                                            implicitHeight: detailsText.implicitHeight + 20

                                            Text {
                                                id: detailsText
                                                anchors.fill: parent
                                                anchors.margins: 10
                                                text: modelData.details.length > 0 ? modelData.details : modelData.entityId
                                                color: themeModel.textMuted
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 10
                                                wrapMode: Text.WordWrap
                                                renderType: Text.NativeRendering
                                            }
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            text: "Raw state: " + modelData.rawState
                                            color: themeModel.textMuted
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 9
                                            wrapMode: Text.WordWrap
                                            renderType: Text.NativeRendering
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