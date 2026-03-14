import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Effects

Window {
    id: root
    visible: false
    opacity: 0
    color: "transparent"
    title: "CyberDock"
    flags: Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint

    property var colors: backend.palette
    property bool hiddenState: backend.autoHide && !hoverTracker.containsMouse && !settingsPopup.opened
    property int appButtonHeight: Math.max(64, backend.itemHeight)
    property int iconBoxSize: Math.min(48, Math.max(44, appButtonHeight - 24))

    function refreshGeometry() {
        var contentWidth = panel.implicitWidth + 36
        var contentHeight = panel.implicitHeight + 24
        var g = backend.targetGeometry(contentWidth, contentHeight, hiddenState)
        root.x = g.x
        root.y = g.y
        root.width = g.width
        root.height = g.height
        backend.syncWindowGeometry(root.x, root.y, root.width, root.height, hiddenState)
    }

    onHiddenStateChanged: refreshGeometry()
    onWidthChanged: backend.syncWindowGeometry(x, y, width, height, hiddenState)
    onHeightChanged: backend.syncWindowGeometry(x, y, width, height, hiddenState)
    onXChanged: backend.syncWindowGeometry(x, y, width, height, hiddenState)
    onYChanged: backend.syncWindowGeometry(x, y, width, height, hiddenState)

    Component.onCompleted: {
        refreshGeometry()
    }

    function showDock() {
        visible = true
        appear.restart()
    }

    Connections {
        target: backend
        function onConfigChanged() { refreshGeometry() }
    }

    Behavior on y {
        NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
    }

    Behavior on opacity {
        NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
    }

    NumberAnimation {
        id: appear
        target: root
        property: "opacity"
        from: 0
        to: 1
        duration: 180
        easing.type: Easing.OutCubic
    }

    HoverHandler {
        id: hoverTracker
    }

    Timer {
        id: relayoutTimer
        interval: 16
        repeat: false
        onTriggered: refreshGeometry()
    }

    Rectangle {
        id: glow
        anchors.horizontalCenter: panel.horizontalCenter
        anchors.bottom: panel.bottom
        width: Math.max(320, panel.width - 80)
        height: 100
        radius: 50
        color: colors.glowStart
        opacity: 0.8
        visible: true
    }

    MultiEffect {
        anchors.fill: glow
        source: glow
        blurEnabled: true
        blurMax: 32
        blur: 1
        opacity: 0.5
    }

    Rectangle {
        id: panel
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
        implicitWidth: contentRow.implicitWidth + 32
        implicitHeight: Math.max(appButtonHeight + 28, 88)
        radius: 30
        color: colors.panelBg
        border.width: 1
        border.color: colors.panelBorder
        clip: true

        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: colors.shadow
            shadowVerticalOffset: 18
            shadowBlur: 1
            shadowScale: 1.08
        }

        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.0; color: colors.glowStart }
                GradientStop { position: 1.0; color: colors.glowEnd }
            }
            opacity: 0.22
        }

        RowLayout {
            id: contentRow
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12

            ToolButton {
                id: launcherButton
                Layout.preferredWidth: 44
                Layout.preferredHeight: 44
                text: backend.glyph("apps")
                font.family: backend.materialFontFamily
                font.pixelSize: 20
                hoverEnabled: true
                onClicked: backend.openLauncher()
                background: Rectangle {
                    radius: width / 2
                    color: launcherButton.hovered ? colors.hoverBg : "transparent"
                    border.width: 1
                    border.color: launcherButton.hovered ? colors.utilityBorder : "transparent"
                }
                contentItem: Text {
                    text: launcherButton.text
                    color: colors.icon
                    font.family: backend.materialFontFamily
                    font.pixelSize: 20
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }

            Rectangle {
                width: 1
                height: 28
                color: colors.separator
            }

            Flickable {
                id: appsFlick
                Layout.fillWidth: true
                Layout.preferredWidth: Math.max(120, appsRow.width)
                Layout.preferredHeight: appButtonHeight
                implicitWidth: Math.max(120, appsRow.width)
                contentWidth: appsRow.width
                contentHeight: height
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                flickableDirection: Flickable.HorizontalFlick

                ScrollBar.horizontal: ScrollBar {
                    policy: ScrollBar.AlwaysOff
                }

                Row {
                    id: appsRow
                    spacing: 8
                    height: appsFlick.height

                    Repeater {
                        model: backend.items

                        delegate: Item {
                            width: 60
                            height: appButtonHeight

                            property bool focused: !!modelData.focused
                            property bool running: (modelData.running || 0) > 0

                            Rectangle {
                                id: appShell
                                anchors.fill: parent
                                radius: 20
                                color: focused ? colors.focusedBg : (running ? colors.runningBg : "transparent")
                                border.width: 1
                                border.color: focused ? colors.focusedBorder : (running ? colors.runningBorder : "transparent")

                                Behavior on color { ColorAnimation { duration: 120 } }
                                Behavior on border.color { ColorAnimation { duration: 120 } }

                                Column {
                                    anchors.centerIn: parent
                                    spacing: 4

                                    Rectangle {
                                        width: iconBoxSize
                                        height: iconBoxSize
                                        radius: 16
                                        color: "transparent"
                                        anchors.horizontalCenter: parent.horizontalCenter

                                        Image {
                                            id: appIcon
                                            anchors.centerIn: parent
                                            width: Math.min(34, Math.max(30, iconBoxSize - 12))
                                            height: width
                                            fillMode: Image.PreserveAspectFit
                                            source: modelData.iconPath || ""
                                            smooth: true
                                            visible: source !== ""
                                        }

                                        Text {
                                            anchors.centerIn: parent
                                            visible: !appIcon.visible
                                            text: String(modelData.name || "?").slice(0, 1).toUpperCase()
                                            color: colors.text
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 18
                                            font.bold: true
                                        }
                                    }

                                    Rectangle {
                                        width: 6
                                        height: 6
                                        radius: 3
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        color: running ? colors.dot : "transparent"
                                    }
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                                hoverEnabled: true
                                onEntered: appShell.color = focused ? colors.focusedBg : colors.hoverBg
                                onExited: appShell.color = focused ? colors.focusedBg : (running ? colors.runningBg : "transparent")
                                onClicked: function(mouse) {
                                    if (mouse.button === Qt.MiddleButton) {
                                        backend.openNewItem(modelData.itemId)
                                    } else {
                                        backend.activateItem(modelData.itemId)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Item {
                Layout.fillWidth: true
                visible: backend.iconsLeft
                implicitWidth: backend.iconsLeft ? 1 : 0
            }

            Rectangle {
                width: 1
                height: 28
                color: colors.separator
            }

            Text {
                Layout.alignment: Qt.AlignVCenter
                text: backend.clockText
                color: colors.textMuted
                font.family: backend.monoFontFamily
                font.pixelSize: 11
                font.weight: Font.DemiBold
                padding: 8
            }

            ToolButton {
                id: volumeButton
                Layout.preferredWidth: 42
                Layout.preferredHeight: 42
                text: backend.volumeIcon
                hoverEnabled: true
                onClicked: backend.toggleMute()
                background: Rectangle {
                    radius: width / 2
                    color: volumeButton.hovered ? colors.volumePill : "transparent"
                    border.width: 1
                    border.color: volumeButton.hovered ? colors.utilityBorder : "transparent"
                }
                contentItem: Text {
                    text: volumeButton.text
                    color: colors.icon
                    font.family: backend.materialFontFamily
                    font.pixelSize: 18
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                WheelHandler {
                    onWheel: function(event) {
                        backend.changeVolume(event.angleDelta.y > 0 ? 5 : -5)
                    }
                }
            }

            ToolButton {
                id: settingsButton
                Layout.preferredWidth: 42
                Layout.preferredHeight: 42
                text: backend.glyph("settings")
                hoverEnabled: true
                onClicked: settingsPopup.opened ? settingsPopup.close() : settingsPopup.open()
                background: Rectangle {
                    radius: width / 2
                    color: settingsButton.hovered || settingsPopup.opened ? colors.hoverBg : "transparent"
                    border.width: 1
                    border.color: settingsButton.hovered || settingsPopup.opened ? colors.utilityBorder : "transparent"
                }
                contentItem: Text {
                    text: settingsButton.text
                    color: colors.icon
                    font.family: backend.materialFontFamily
                    font.pixelSize: 18
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
    }

    Popup {
        id: settingsPopup
        x: root.width - width - 20
        y: root.height - height - panel.height - 18
        width: 320
        height: 420
        padding: 0
        modal: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            radius: 28
            color: Qt.alpha(colors.panelBg, 0.98)
            border.width: 1
            border.color: colors.panelBorder
        }

        contentItem: ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 14

            RowLayout {
                Layout.fillWidth: true

                ColumnLayout {
                    spacing: 2
                    Text {
                        text: "Dock settings"
                        color: colors.text
                        font.family: "Outfit"
                        font.pixelSize: 18
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: "Native preview with the same dock.toml"
                        color: colors.textMuted
                        font.family: backend.uiFontFamily
                        font.pixelSize: 12
                    }
                }

                Item { Layout.fillWidth: true }

                ToolButton {
                    text: backend.glyph("open_in_new")
                    onClicked: backend.openDockConfig()
                    background: Rectangle {
                        radius: width / 2
                        color: parent.hovered ? colors.hoverBg : "transparent"
                    }
                    contentItem: Text {
                        text: parent.text
                        color: colors.icon
                        font.family: backend.materialFontFamily
                        font.pixelSize: 16
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 1
                color: colors.separator
            }

            SwitchDelegate {
                Layout.fillWidth: true
                text: "Auto-hide"
                checked: backend.autoHide
                onToggled: backend.autoHide = checked
                indicator: Rectangle {
                    implicitWidth: 42
                    implicitHeight: 26
                    radius: 13
                    color: parent.checked ? colors.focusedBg : colors.utilityBg
                    border.width: 1
                    border.color: parent.checked ? colors.focusedBorder : colors.utilityBorder
                    Rectangle {
                        width: 18
                        height: 18
                        radius: 9
                        x: parent.checked ? 20 : 4
                        y: 4
                        color: colors.text
                        Behavior on x { NumberAnimation { duration: 120 } }
                    }
                }
                contentItem: Text {
                    text: parent.text
                    color: colors.text
                    font.family: backend.uiFontFamily
                    font.pixelSize: 14
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: "transparent"
                }
            }

            SwitchDelegate {
                Layout.fillWidth: true
                text: "Keep icons left"
                checked: backend.iconsLeft
                onToggled: backend.iconsLeft = checked
                indicator: Rectangle {
                    implicitWidth: 42
                    implicitHeight: 26
                    radius: 13
                    color: parent.checked ? colors.focusedBg : colors.utilityBg
                    border.width: 1
                    border.color: parent.checked ? colors.focusedBorder : colors.utilityBorder
                    Rectangle {
                        width: 18
                        height: 18
                        radius: 9
                        x: parent.checked ? 20 : 4
                        y: 4
                        color: colors.text
                        Behavior on x { NumberAnimation { duration: 120 } }
                    }
                }
                contentItem: Text {
                    text: parent.text
                    color: colors.text
                    font.family: backend.uiFontFamily
                    font.pixelSize: 14
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle { color: "transparent" }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "Position"
                    color: colors.textMuted
                    font.family: backend.uiFontFamily
                    font.pixelSize: 12
                }

                ComboBox {
                    Layout.fillWidth: true
                    model: [
                        { label: "Left", value: "left" },
                        { label: "Center", value: "center" },
                        { label: "Right", value: "right" }
                    ]
                    textRole: "label"
                    currentIndex: {
                        for (var i = 0; i < model.length; i++) {
                            if (model[i].value === backend.position) {
                                return i
                            }
                        }
                        return 1
                    }
                    onActivated: backend.position = model[index].value
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "Width"
                    color: colors.textMuted
                    font.family: backend.uiFontFamily
                    font.pixelSize: 12
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    SpinBox {
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        value: backend.dockWidth
                        editable: true
                        onValueModified: backend.dockWidth = value
                    }

                    ComboBox {
                        Layout.preferredWidth: 90
                        model: ["%", "px"]
                        currentIndex: backend.dockWidthUnit === "%" ? 0 : 1
                        onActivated: backend.dockWidthUnit = model[index]
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "Icon height"
                    color: colors.textMuted
                    font.family: backend.uiFontFamily
                    font.pixelSize: 12
                }

                Slider {
                    Layout.fillWidth: true
                    from: 64
                    to: 120
                    value: backend.itemHeight
                    onMoved: backend.itemHeight = Math.round(value)
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "Transparency"
                    color: colors.textMuted
                    font.family: backend.uiFontFamily
                    font.pixelSize: 12
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Slider {
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        value: backend.transparency
                        onMoved: backend.transparency = Math.round(value)
                    }

                    Text {
                        text: Math.round(backend.transparency) + "%"
                        color: colors.text
                        font.family: backend.monoFontFamily
                        font.pixelSize: 12
                    }
                }
            }
        }
    }
}
