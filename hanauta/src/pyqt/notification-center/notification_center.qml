import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Window {
    id: root

    width: backend.ncWidth
    height: backend.ncHeight
    visible: true
    color: "transparent"
    title: "Hanauta Notification Center"
    flags: Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint

    property var colors: backend.palette
    property int settingsSection: 0
    property date now: new Date()
    property color mediaControlColor: Qt.rgba(1, 1, 1, 0.78)

    function glyph(name) {
        return backend.materialIcon(name)
    }

    function clamp(value, minimum, maximum) {
        return Math.max(minimum, Math.min(maximum, value))
    }

    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: root.now = new Date()
    }

    component IconButton: RoundButton {
        id: iconButton

        property string iconName: ""
        property color foreground: colors.icon
        property color restingColor: colors.cardStrongBg
        property color hoverColor: colors.hoverBg

        implicitWidth: 40
        implicitHeight: 40
        hoverEnabled: true
        padding: 0

        contentItem: Text {
            text: root.glyph(iconButton.iconName)
            color: iconButton.foreground
            font.family: backend.materialFontFamily
            font.pixelSize: 19
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        background: Rectangle {
            radius: width / 2
            color: iconButton.down || iconButton.hovered
                   ? iconButton.hoverColor
                   : iconButton.restingColor
            border.width: 1
            border.color: colors.panelBorder

            Behavior on color {
                ColorAnimation { duration: 120 }
            }
        }

        scale: down ? 0.94 : 1.0

        Behavior on scale {
            NumberAnimation { duration: 90; easing.type: Easing.OutCubic }
        }
    }

    component ActionButton: Button {
        id: actionButton

        property bool emphasized: false
        property bool destructive: false

        implicitHeight: 38
        leftPadding: 16
        rightPadding: 16
        hoverEnabled: true

        contentItem: Text {
            text: actionButton.text
            color: actionButton.destructive
                   ? colors.dangerFg
                   : actionButton.emphasized
                     ? colors.onPrimary
                     : colors.text
            font.family: backend.uiFontFamily
            font.pixelSize: 11
            font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }

        background: Rectangle {
            radius: 13
            color: actionButton.destructive
                   ? colors.dangerBg
                   : actionButton.emphasized
                     ? colors.primary
                     : actionButton.hovered
                       ? colors.hoverBg
                       : colors.cardStrongBg
            border.width: actionButton.emphasized ? 0 : 1
            border.color: colors.panelBorder

            Behavior on color {
                ColorAnimation { duration: 120 }
            }
        }

        scale: down ? 0.97 : 1.0

        Behavior on scale {
            NumberAnimation { duration: 90; easing.type: Easing.OutCubic }
        }
    }

    component SurfaceCard: Rectangle {
        radius: 22
        color: colors.cardBg
        border.width: 1
        border.color: colors.panelBorder

        Behavior on color {
            ColorAnimation { duration: 180 }
        }
    }

    component SectionHeader: RowLayout {
        id: sectionHeader

        property string title: ""
        property string detail: ""

        Layout.fillWidth: true
        spacing: 8

        Text {
            text: sectionHeader.title
            color: colors.text
            font.family: backend.uiFontFamily
            font.pixelSize: 13
            font.weight: Font.DemiBold
        }

        Item { Layout.fillWidth: true }

        Text {
            visible: sectionHeader.detail.length > 0
            text: sectionHeader.detail
            color: colors.inactive
            font.family: backend.uiFontFamily
            font.pixelSize: 9
        }
    }

    component ControlSlider: SurfaceCard {
        id: controlCard

        property string iconName: ""
        property string title: ""
        property real controlValue: 0
        property string valueSuffix: "%"
        signal edited(real value)

        Layout.fillWidth: true
        Layout.preferredHeight: 58
        radius: 18

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 12
            spacing: 11

            Rectangle {
                Layout.preferredWidth: 34
                Layout.preferredHeight: 34
                radius: 12
                color: colors.accentSoft

                Text {
                    anchors.centerIn: parent
                    text: root.glyph(controlCard.iconName)
                    color: colors.primary
                    font.family: backend.materialFontFamily
                    font.pixelSize: 18
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                RowLayout {
                    Layout.fillWidth: true

                    Text {
                        text: controlCard.title
                        color: colors.text
                        font.family: backend.uiFontFamily
                        font.pixelSize: 10
                        font.weight: Font.Medium
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: Math.round(controlSlider.value) + controlCard.valueSuffix
                        color: colors.textMuted
                        font.family: backend.monoFontFamily
                        font.pixelSize: 9
                    }
                }

                Slider {
                    id: controlSlider

                    Layout.fillWidth: true
                    Layout.preferredHeight: 18
                    from: 0
                    to: 100
                    value: controlCard.controlValue
                    live: true
                    padding: 0
                    onMoved: controlCard.edited(value)

                    background: Rectangle {
                        x: controlSlider.leftPadding
                        y: controlSlider.topPadding + (controlSlider.availableHeight - height) / 2
                        width: controlSlider.availableWidth
                        height: 5
                        radius: height / 2
                        color: colors.cardStrongBg

                        Rectangle {
                            width: parent.width * controlSlider.visualPosition
                            height: parent.height
                            radius: parent.radius
                            color: colors.primary
                        }
                    }

                    handle: Rectangle {
                        x: controlSlider.leftPadding
                           + controlSlider.visualPosition
                           * (controlSlider.availableWidth - width)
                        y: controlSlider.topPadding
                           + (controlSlider.availableHeight - height) / 2
                        implicitWidth: controlSlider.pressed ? 15 : 13
                        implicitHeight: implicitWidth
                        radius: width / 2
                        color: colors.primary
                        border.width: 3
                        border.color: colors.panelBg

                        Behavior on implicitWidth {
                            NumberAnimation { duration: 100 }
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"

        Rectangle {
            id: panel

            width: parent.width - 18
            height: parent.height - 18
            anchors.centerIn: parent
            radius: 30
            color: colors.panelBg
            border.width: 1
            border.color: colors.panelBorder
            clip: true
            opacity: 0
            scale: 0.975

            ParallelAnimation {
                running: true

                NumberAnimation {
                    target: panel
                    property: "opacity"
                    from: 0
                    to: 1
                    duration: 190
                    easing.type: Easing.OutCubic
                }

                NumberAnimation {
                    target: panel
                    property: "scale"
                    from: 0.975
                    to: 1
                    duration: 240
                    easing.type: Easing.OutBack
                    easing.overshoot: 0.75
                }
            }

            Rectangle {
                width: 280
                height: 280
                radius: width / 2
                x: -112
                y: -138
                color: colors.accentSoft
                opacity: 0.22
            }

            Rectangle {
                width: 210
                height: 210
                radius: width / 2
                anchors.right: parent.right
                anchors.rightMargin: -105
                anchors.verticalCenter: parent.verticalCenter
                color: colors.tertiary
                opacity: 0.055
            }

            Rectangle {
                width: 170
                height: 170
                radius: width / 2
                anchors.right: parent.right
                anchors.rightMargin: -70
                anchors.bottom: parent.bottom
                anchors.bottomMargin: -55
                color: colors.primary
                opacity: 0.08
            }

            StackLayout {
                id: mainStack

                anchors.fill: parent
                currentIndex: 0

                Item {
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 18
                        anchors.rightMargin: 18
                        anchors.topMargin: 16
                        anchors.bottomMargin: 14
                        spacing: 12

                        RowLayout {
                            id: topHeader

                            Layout.fillWidth: true
                            Layout.preferredHeight: 62
                            spacing: 12

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: -1

                                Text {
                                    text: Qt.formatTime(root.now, "hh:mm")
                                    color: colors.text
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 27
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: -0.5
                                }

                                Text {
                                    text: Qt.formatDate(root.now, "dddd, d MMMM")
                                    color: colors.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 10
                                }
                            }

                            IconButton {
                                iconName: "settings"
                                onClicked: mainStack.currentIndex = 1
                            }

                            IconButton {
                                iconName: "close"
                                foreground: colors.dangerFg
                                restingColor: colors.dangerBg
                                hoverColor: colors.dangerBg
                                onClicked: backend.closeCenter()
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 42
                            radius: 15
                            color: colors.cardBg
                            border.width: 1
                            border.color: colors.panelBorder

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 11
                                anchors.rightMargin: 12
                                spacing: 9

                                Rectangle {
                                    Layout.preferredWidth: 26
                                    Layout.preferredHeight: 26
                                    radius: 9
                                    gradient: Gradient {
                                        GradientStop { position: 0.0; color: colors.primary }
                                        GradientStop { position: 1.0; color: colors.tertiary }
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        text: root.glyph("person")
                                        color: colors.onPrimary
                                        font.family: backend.materialFontFamily
                                        font.pixelSize: 15
                                    }
                                }

                                Text {
                                    text: backend.username
                                    color: colors.text
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                }

                                Item { Layout.fillWidth: true }

                                Rectangle {
                                    Layout.preferredWidth: 6
                                    Layout.preferredHeight: 6
                                    radius: 3
                                    color: colors.phoneOnline
                                }

                                Text {
                                    text: "up " + backend.uptime
                                    color: colors.textMuted
                                    font.family: backend.monoFontFamily
                                    font.pixelSize: 9
                                }
                            }
                        }

                        ScrollView {
                            id: overviewView

                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            hoverEnabled: true
                            contentWidth: availableWidth
                            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                            ScrollBar.vertical: ScrollBar {
                                policy: ScrollBar.AsNeeded
                                width: 4
                                opacity: overviewView.hovered || active ? 0.48 : 0.0

                                Behavior on opacity {
                                    NumberAnimation { duration: 120 }
                                }

                                contentItem: Rectangle {
                                    implicitWidth: 4
                                    implicitHeight: 72
                                    radius: 2
                                    color: colors.primary
                                }

                                background: Rectangle { color: "transparent" }
                            }

                            ColumnLayout {
                                width: overviewView.availableWidth
                                spacing: 12

                                SectionHeader {
                                    title: "Quick controls"
                                    detail: "Click to toggle"
                                }

                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 2
                                    rowSpacing: 9
                                    columnSpacing: 9

                                    Repeater {
                                        model: backend.quickSettings

                                        delegate: Rectangle {
                                            id: quickTile

                                            required property var modelData
                                            required property int index

                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 74
                                            radius: 20
                                            border.width: 1
                                            border.color: modelData.active
                                                          ? Qt.rgba(colors.primary.r,
                                                                    colors.primary.g,
                                                                    colors.primary.b,
                                                                    0.85)
                                                          : colors.panelBorder
                                            gradient: Gradient {
                                                GradientStop {
                                                    position: 0.0
                                                    color: quickTile.modelData.active
                                                           ? colors.primary
                                                           : colors.cardBg
                                                }
                                                GradientStop {
                                                    position: 1.0
                                                    color: quickTile.modelData.active
                                                           ? colors.tertiary
                                                           : colors.cardBg
                                                }
                                            }
                                            scale: tileMouse.pressed
                                                   ? 0.975
                                                   : tileMouse.containsMouse
                                                     ? 1.012
                                                     : 1.0

                                            Behavior on scale {
                                                NumberAnimation {
                                                    duration: 110
                                                    easing.type: Easing.OutCubic
                                                }
                                            }

                                            MouseArea {
                                                id: tileMouse

                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: Qt.PointingHandCursor
                                                onClicked: backend.toggleQuickSetting(quickTile.modelData.key)
                                            }

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.margins: 12
                                                spacing: 10

                                                Rectangle {
                                                    Layout.preferredWidth: 38
                                                    Layout.preferredHeight: 38
                                                    radius: 13
                                                    color: quickTile.modelData.active
                                                           ? Qt.rgba(1, 1, 1, 0.16)
                                                           : colors.cardStrongBg

                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: root.glyph(quickTile.modelData.icon)
                                                        color: quickTile.modelData.active
                                                               ? colors.onPrimary
                                                               : colors.primary
                                                        font.family: backend.materialFontFamily
                                                        font.pixelSize: 19
                                                    }
                                                }

                                                ColumnLayout {
                                                    Layout.fillWidth: true
                                                    spacing: 1

                                                    Text {
                                                        Layout.fillWidth: true
                                                        text: quickTile.modelData.title
                                                        color: quickTile.modelData.active
                                                               ? colors.onPrimary
                                                               : colors.text
                                                        font.family: backend.uiFontFamily
                                                        font.pixelSize: 11
                                                        font.weight: Font.DemiBold
                                                        elide: Text.ElideRight
                                                    }

                                                    Text {
                                                        Layout.fillWidth: true
                                                        text: quickTile.modelData.subtitle
                                                        color: quickTile.modelData.active
                                                               ? Qt.rgba(1, 1, 1, 0.72)
                                                               : colors.textMuted
                                                        font.family: backend.uiFontFamily
                                                        font.pixelSize: 9
                                                        elide: Text.ElideRight
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                SectionHeader {
                                    title: "Controls"
                                    detail: "System"
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    ControlSlider {
                                        iconName: "brightness_medium"
                                        title: "Brightness"
                                        controlValue: backend.brightness
                                        onEdited: value => backend.setBrightness(Math.round(value))
                                    }

                                    ControlSlider {
                                        iconName: backend.volume <= 0
                                                  ? "volume_off"
                                                  : backend.volume < 45
                                                    ? "volume_down"
                                                    : "volume_up"
                                        title: "Volume"
                                        controlValue: backend.volume
                                        onEdited: value => backend.setVolume(Math.round(value))
                                    }
                                }

                                SectionHeader {
                                    title: "Now playing"
                                    detail: backend.mediaStatus || "Idle"
                                }

                                Rectangle {
                                    id: mediaCard

                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 178
                                    radius: 24
                                    clip: true
                                    border.width: 1
                                    border.color: colors.mediaBorder
                                    gradient: Gradient {
                                        GradientStop { position: 0.0; color: colors.mediaStart }
                                        GradientStop { position: 0.58; color: colors.mediaEnd }
                                        GradientStop { position: 1.0; color: colors.panelBg }
                                    }

                                    Rectangle {
                                        anchors.fill: parent
                                        color: "#72000000"
                                    }

                                    Rectangle {
                                        width: 190
                                        height: 190
                                        radius: width / 2
                                        anchors.right: parent.right
                                        anchors.rightMargin: -70
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: colors.primary
                                        opacity: 0.11
                                    }

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 11

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 13

                                            Rectangle {
                                                Layout.preferredWidth: 74
                                                Layout.preferredHeight: 74
                                                radius: 18
                                                clip: true
                                                color: colors.cardStrongBg
                                                border.width: 1
                                                border.color: colors.mediaBorder

                                                Image {
                                                    anchors.fill: parent
                                                    source: backend.mediaCover
                                                    fillMode: Image.PreserveAspectCrop
                                                    asynchronous: true
                                                    visible: String(backend.mediaCover || "").length > 0
                                                }

                                                Text {
                                                    anchors.centerIn: parent
                                                    visible: String(backend.mediaCover || "").length === 0
                                                    text: root.glyph("music_note")
                                                    color: colors.primary
                                                    font.family: backend.materialFontFamily
                                                    font.pixelSize: 28
                                                }
                                            }

                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 4

                                                Rectangle {
                                                    Layout.preferredWidth: 64
                                                    Layout.preferredHeight: 20
                                                    radius: 8
                                                    color: Qt.rgba(1, 1, 1, 0.11)

                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: "PLAYING"
                                                        color: root.mediaControlColor
                                                        font.family: backend.uiFontFamily
                                                        font.pixelSize: 8
                                                        font.weight: Font.Bold
                                                        font.letterSpacing: 1.1
                                                    }
                                                }

                                                Text {
                                                    Layout.fillWidth: true
                                                    text: backend.mediaTitle || "Nothing playing"
                                                    color: colors.text
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 15
                                                    font.weight: Font.DemiBold
                                                    elide: Text.ElideRight
                                                }

                                                Text {
                                                    Layout.fillWidth: true
                                                    text: backend.mediaArtist || "Start audio in any MPRIS player"
                                                    color: colors.primary
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 10
                                                    elide: Text.ElideRight
                                                }
                                            }
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 4

                                            Rectangle {
                                                Layout.fillWidth: true
                                                Layout.preferredHeight: 4
                                                radius: 2
                                                color: Qt.rgba(1, 1, 1, 0.14)

                                                Rectangle {
                                                    width: parent.width
                                                           * root.clamp(backend.mediaProgress || 0, 0, 1)
                                                    height: parent.height
                                                    radius: parent.radius
                                                    color: colors.primary

                                                    Behavior on width {
                                                        NumberAnimation { duration: 180 }
                                                    }
                                                }
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true

                                                Text {
                                                    text: backend.mediaElapsed
                                                    color: root.mediaControlColor
                                                    font.family: backend.monoFontFamily
                                                    font.pixelSize: 8
                                                }

                                                Item { Layout.fillWidth: true }

                                                Text {
                                                    text: backend.mediaTotal
                                                    color: root.mediaControlColor
                                                    font.family: backend.monoFontFamily
                                                    font.pixelSize: 8
                                                }
                                            }
                                        }

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 10

                                            Item { Layout.fillWidth: true }

                                            IconButton {
                                                iconName: "skip_previous"
                                                foreground: root.mediaControlColor
                                                restingColor: "transparent"
                                                hoverColor: Qt.rgba(1, 1, 1, 0.10)
                                                onClicked: backend.triggerMediaAction("previous")
                                            }

                                            IconButton {
                                                implicitWidth: 46
                                                implicitHeight: 46
                                                iconName: backend.mediaStatus === "Playing"
                                                          ? "pause"
                                                          : "play_arrow"
                                                foreground: colors.playFg
                                                restingColor: colors.primary
                                                hoverColor: colors.primary
                                                onClicked: backend.triggerMediaAction("toggle")
                                            }

                                            IconButton {
                                                iconName: "skip_next"
                                                foreground: root.mediaControlColor
                                                restingColor: "transparent"
                                                hoverColor: Qt.rgba(1, 1, 1, 0.10)
                                                onClicked: backend.triggerMediaAction("next")
                                            }

                                            Item { Layout.fillWidth: true }
                                        }
                                    }
                                }

                                SectionHeader {
                                    title: "Connected devices"
                                    detail: backend.phoneInfo.online ? "Online" : "Offline"
                                }

                                SurfaceCard {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 66
                                    radius: 20

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 11

                                        Rectangle {
                                            Layout.preferredWidth: 40
                                            Layout.preferredHeight: 40
                                            radius: 14
                                            color: colors.cardStrongBg

                                            Text {
                                                anchors.centerIn: parent
                                                text: root.glyph("phone_android")
                                                color: colors.primary
                                                font.family: backend.materialFontFamily
                                                font.pixelSize: 20
                                            }

                                            Rectangle {
                                                width: 9
                                                height: 9
                                                radius: width / 2
                                                anchors.right: parent.right
                                                anchors.bottom: parent.bottom
                                                border.width: 2
                                                border.color: colors.cardBg
                                                color: backend.phoneInfo.online
                                                       ? colors.phoneOnline
                                                       : colors.phoneOffline
                                            }
                                        }

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 2

                                            Text {
                                                Layout.fillWidth: true
                                                text: backend.phoneInfo.name || "No phone connected"
                                                color: colors.text
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 11
                                                font.weight: Font.DemiBold
                                                elide: Text.ElideRight
                                            }

                                            Text {
                                                Layout.fillWidth: true
                                                text: backend.phoneInfo.status || "KDE Connect is waiting"
                                                color: colors.textMuted
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 9
                                                elide: Text.ElideRight
                                            }
                                        }

                                        Rectangle {
                                            visible: (backend.phoneInfo.battery || "").length > 0
                                            Layout.preferredWidth: 52
                                            Layout.preferredHeight: 28
                                            radius: 10
                                            color: colors.cardStrongBg

                                            Row {
                                                anchors.centerIn: parent
                                                spacing: 4

                                                Text {
                                                    text: root.glyph("battery_std")
                                                    color: colors.primary
                                                    font.family: backend.materialFontFamily
                                                    font.pixelSize: 14
                                                }

                                                Text {
                                                    text: backend.phoneInfo.battery || ""
                                                    color: colors.text
                                                    font.family: backend.monoFontFamily
                                                    font.pixelSize: 9
                                                }
                                            }
                                        }
                                    }
                                }

                                SurfaceCard {
                                    id: homeAssistantCard

                                    visible: backend.homeAssistantVisible
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: visible
                                                            ? 58 + homeAssistantGrid.implicitHeight
                                                            : 0
                                    radius: 22

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 9

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 9

                                            Rectangle {
                                                Layout.preferredWidth: 34
                                                Layout.preferredHeight: 34
                                                radius: 12
                                                color: colors.accentSoft

                                                Text {
                                                    anchors.centerIn: parent
                                                    text: root.glyph("home")
                                                    color: colors.primary
                                                    font.family: backend.materialFontFamily
                                                    font.pixelSize: 18
                                                }
                                            }

                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 1

                                                Text {
                                                    text: "Home Assistant"
                                                    color: colors.text
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 11
                                                    font.weight: Font.DemiBold
                                                }

                                                Text {
                                                    Layout.fillWidth: true
                                                    text: backend.homeAssistantStatus
                                                    color: colors.textMuted
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 9
                                                    elide: Text.ElideRight
                                                }
                                            }

                                            IconButton {
                                                implicitWidth: 34
                                                implicitHeight: 34
                                                iconName: "tune"
                                                onClicked: backend.openSettingsApp("services")
                                            }
                                        }

                                        GridLayout {
                                            id: homeAssistantGrid

                                            Layout.fillWidth: true
                                            columns: 3
                                            rowSpacing: 7
                                            columnSpacing: 7

                                            Repeater {
                                                model: backend.homeAssistantTiles

                                                delegate: Rectangle {
                                                    id: haTile

                                                    required property var modelData
                                                    required property int index

                                                    Layout.fillWidth: true
                                                    Layout.preferredHeight: 66
                                                    radius: 17
                                                    color: tileArea.containsMouse
                                                           ? colors.hoverBg
                                                           : colors.cardStrongBg
                                                    border.width: 1
                                                    border.color: colors.panelBorder
                                                    opacity: modelData.enabled ? 1.0 : 0.48

                                                    Behavior on color {
                                                        ColorAnimation { duration: 110 }
                                                    }

                                                    MouseArea {
                                                        id: tileArea

                                                        anchors.fill: parent
                                                        enabled: haTile.modelData.enabled
                                                        hoverEnabled: true
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: backend.activateHomeAssistantTile(haTile.index)
                                                    }

                                                    Column {
                                                        anchors.centerIn: parent
                                                        width: parent.width - 12
                                                        spacing: 3

                                                        Text {
                                                            anchors.horizontalCenter: parent.horizontalCenter
                                                            text: root.glyph(haTile.modelData.icon)
                                                            color: colors.primary
                                                            font.family: backend.materialFontFamily
                                                            font.pixelSize: 17
                                                        }

                                                        Text {
                                                            width: parent.width
                                                            text: haTile.modelData.title
                                                            color: colors.text
                                                            font.family: backend.uiFontFamily
                                                            font.pixelSize: 9
                                                            font.weight: Font.DemiBold
                                                            horizontalAlignment: Text.AlignHCenter
                                                            elide: Text.ElideRight
                                                        }

                                                        Text {
                                                            width: parent.width
                                                            text: haTile.modelData.subtitle
                                                            color: colors.textMuted
                                                            font.family: backend.uiFontFamily
                                                            font.pixelSize: 8
                                                            horizontalAlignment: Text.AlignHCenter
                                                            elide: Text.ElideRight
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                Repeater {
                                    model: backend.serviceCards

                                    delegate: SurfaceCard {
                                        id: serviceCard

                                        required property var modelData
                                        required property int index

                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 68
                                        radius: 20

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 12
                                            spacing: 11

                                            Rectangle {
                                                Layout.preferredWidth: 38
                                                Layout.preferredHeight: 38
                                                radius: 13
                                                color: colors.cardStrongBg

                                                Text {
                                                    anchors.centerIn: parent
                                                    text: root.glyph(serviceCard.modelData.icon)
                                                    color: colors.primary
                                                    font.family: backend.materialFontFamily
                                                    font.pixelSize: 18
                                                }
                                            }

                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 2

                                                Text {
                                                    Layout.fillWidth: true
                                                    text: serviceCard.modelData.title
                                                    color: colors.text
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 11
                                                    font.weight: Font.DemiBold
                                                    elide: Text.ElideRight
                                                }

                                                Text {
                                                    Layout.fillWidth: true
                                                    text: serviceCard.modelData.detail
                                                    color: colors.textMuted
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 9
                                                    elide: Text.ElideRight
                                                }
                                            }

                                            IconButton {
                                                implicitWidth: 34
                                                implicitHeight: 34
                                                iconName: "arrow_forward"
                                                onClicked: backend.launchService(serviceCard.modelData.key)
                                            }
                                        }
                                    }
                                }

                                Item { Layout.preferredHeight: 4 }
                            }
                        }
                    }
                }

                Item {
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 18
                        anchors.rightMargin: 18
                        anchors.topMargin: 16
                        anchors.bottomMargin: 16
                        spacing: 12

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 46
                            spacing: 10

                            IconButton {
                                iconName: "arrow_back"
                                onClicked: mainStack.currentIndex = 0
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 0

                                Text {
                                    text: "Center settings"
                                    color: colors.text
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 17
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    text: "Configure without leaving the panel"
                                    color: colors.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 9
                                }
                            }

                            IconButton {
                                iconName: "open_in_new"
                                onClicked: backend.openOverviewSettings()
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 46
                            radius: 16
                            color: colors.cardBg
                            border.width: 1
                            border.color: colors.panelBorder

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 4
                                spacing: 4

                                Repeater {
                                    model: [
                                        { title: "Overview", icon: "monitor_heart" },
                                        { title: "Theme", icon: "palette" },
                                        { title: "Home", icon: "home" }
                                    ]

                                    delegate: Rectangle {
                                        id: settingsTab

                                        required property var modelData
                                        required property int index

                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        radius: 12
                                        color: settingsSection === index
                                               ? colors.primary
                                               : tabArea.containsMouse
                                                 ? colors.hoverBg
                                                 : "transparent"

                                        Behavior on color {
                                            ColorAnimation { duration: 120 }
                                        }

                                        MouseArea {
                                            id: tabArea

                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: settingsSection = settingsTab.index
                                        }

                                        Row {
                                            anchors.centerIn: parent
                                            spacing: 6

                                            Text {
                                                text: root.glyph(settingsTab.modelData.icon)
                                                color: settingsSection === settingsTab.index
                                                       ? colors.onPrimary
                                                       : colors.icon
                                                font.family: backend.materialFontFamily
                                                font.pixelSize: 15
                                            }

                                            Text {
                                                text: settingsTab.modelData.title
                                                color: settingsSection === settingsTab.index
                                                       ? colors.onPrimary
                                                       : colors.text
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 9
                                                font.weight: Font.DemiBold
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        StackLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            currentIndex: settingsSection

                            ScrollView {
                                id: systemOverviewView

                                clip: true
                                contentWidth: availableWidth
                                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                                ColumnLayout {
                                    width: systemOverviewView.availableWidth
                                    spacing: 12

                                    SurfaceCard {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 92
                                        radius: 22

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 14
                                            spacing: 12

                                            Rectangle {
                                                Layout.preferredWidth: 54
                                                Layout.preferredHeight: 54
                                                radius: 18
                                                gradient: Gradient {
                                                    GradientStop { position: 0.0; color: colors.primary }
                                                    GradientStop { position: 1.0; color: colors.tertiary }
                                                }

                                                Text {
                                                    anchors.centerIn: parent
                                                    text: root.glyph("computer")
                                                    color: colors.onPrimary
                                                    font.family: backend.materialFontFamily
                                                    font.pixelSize: 25
                                                }
                                            }

                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 3

                                                Text {
                                                    text: "System overview"
                                                    color: colors.text
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 14
                                                    font.weight: Font.DemiBold
                                                }

                                                Text {
                                                    Layout.fillWidth: true
                                                    text: "Live information from this i3 session and the Hanauta shell."
                                                    color: colors.textMuted
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 9
                                                    wrapMode: Text.WordWrap
                                                }
                                            }
                                        }
                                    }

                                    GridLayout {
                                        Layout.fillWidth: true
                                        columns: 2
                                        rowSpacing: 9
                                        columnSpacing: 9

                                        Repeater {
                                            model: backend.systemOverview

                                            delegate: SurfaceCard {
                                                id: overviewMetric

                                                required property var modelData
                                                required property int index

                                                Layout.fillWidth: true
                                                Layout.preferredHeight: 86
                                                radius: 19

                                                ColumnLayout {
                                                    anchors.fill: parent
                                                    anchors.margins: 12
                                                    spacing: 5

                                                    Text {
                                                        Layout.fillWidth: true
                                                        text: overviewMetric.modelData.label
                                                        color: colors.inactive
                                                        font.family: backend.uiFontFamily
                                                        font.pixelSize: 9
                                                        font.weight: Font.Medium
                                                        font.capitalization: Font.AllUppercase
                                                        font.letterSpacing: 0.6
                                                        elide: Text.ElideRight
                                                    }

                                                    Text {
                                                        Layout.fillWidth: true
                                                        text: overviewMetric.modelData.value
                                                        color: colors.text
                                                        font.family: backend.uiFontFamily
                                                        font.pixelSize: 12
                                                        font.weight: Font.DemiBold
                                                        wrapMode: Text.WordWrap
                                                        maximumLineCount: 2
                                                        elide: Text.ElideRight
                                                    }

                                                    Item { Layout.fillHeight: true }

                                                    Rectangle {
                                                        Layout.fillWidth: true
                                                        Layout.preferredHeight: 3
                                                        radius: 2
                                                        color: colors.cardStrongBg

                                                        Rectangle {
                                                            width: parent.width * 0.62
                                                            height: parent.height
                                                            radius: parent.radius
                                                            color: colors.primary
                                                            opacity: 0.72
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            ScrollView {
                                id: appearanceView

                                clip: true
                                contentWidth: availableWidth
                                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                                ColumnLayout {
                                    width: appearanceView.availableWidth
                                    spacing: 12

                                    SurfaceCard {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 166
                                        radius: 24
                                        clip: true

                                        Rectangle {
                                            width: 170
                                            height: 170
                                            radius: width / 2
                                            x: -64
                                            y: -72
                                            color: colors.accentSoft
                                            opacity: 0.55
                                        }

                                        Rectangle {
                                            width: 120
                                            height: 120
                                            radius: width / 2
                                            anchors.right: parent.right
                                            anchors.rightMargin: -45
                                            anchors.bottom: parent.bottom
                                            anchors.bottomMargin: -28
                                            color: colors.primary
                                            opacity: 0.16
                                        }

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 16
                                            spacing: 8

                                            Text {
                                                text: "Appearance"
                                                color: colors.text
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 16
                                                font.weight: Font.DemiBold
                                            }

                                            Text {
                                                Layout.fillWidth: true
                                                text: "Choose a Hanauta accent. The panel updates immediately through your palette backend."
                                                color: colors.textMuted
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 10
                                                wrapMode: Text.WordWrap
                                            }

                                            Item { Layout.fillHeight: true }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 8

                                                Rectangle {
                                                    Layout.preferredWidth: 42
                                                    Layout.preferredHeight: 42
                                                    radius: 14
                                                    color: colors.primary
                                                }

                                                Rectangle {
                                                    Layout.preferredWidth: 42
                                                    Layout.preferredHeight: 42
                                                    radius: 14
                                                    color: colors.tertiary
                                                }

                                                Rectangle {
                                                    Layout.preferredWidth: 42
                                                    Layout.preferredHeight: 42
                                                    radius: 14
                                                    color: colors.accentSoft
                                                }

                                                Item { Layout.fillWidth: true }

                                                Text {
                                                    text: root.glyph("auto_awesome")
                                                    color: colors.primary
                                                    font.family: backend.materialFontFamily
                                                    font.pixelSize: 24
                                                }
                                            }
                                        }
                                    }

                                    SectionHeader {
                                        title: "Accent presets"
                                        detail: "Live preview"
                                    }

                                    GridLayout {
                                        Layout.fillWidth: true
                                        columns: 3
                                        columnSpacing: 8
                                        rowSpacing: 8

                                        Repeater {
                                            model: [
                                                { key: "orchid", title: "Orchid", icon: "local_florist" },
                                                { key: "mint", title: "Mint", icon: "eco" },
                                                { key: "sunset", title: "Sunset", icon: "wb_twilight" }
                                            ]

                                            delegate: Rectangle {
                                                id: accentPreset

                                                required property var modelData
                                                required property int index

                                                Layout.fillWidth: true
                                                Layout.preferredHeight: 86
                                                radius: 19
                                                color: presetMouse.containsMouse
                                                       ? colors.hoverBg
                                                       : colors.cardBg
                                                border.width: 1
                                                border.color: colors.panelBorder

                                                Behavior on color {
                                                    ColorAnimation { duration: 120 }
                                                }

                                                MouseArea {
                                                    id: presetMouse

                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: backend.setAccent(accentPreset.modelData.key)
                                                }

                                                Column {
                                                    anchors.centerIn: parent
                                                    width: parent.width - 12
                                                    spacing: 6

                                                    Text {
                                                        anchors.horizontalCenter: parent.horizontalCenter
                                                        text: root.glyph(accentPreset.modelData.icon)
                                                        color: colors.primary
                                                        font.family: backend.materialFontFamily
                                                        font.pixelSize: 22
                                                    }

                                                    Text {
                                                        width: parent.width
                                                        text: accentPreset.modelData.title
                                                        color: colors.text
                                                        font.family: backend.uiFontFamily
                                                        font.pixelSize: 10
                                                        font.weight: Font.DemiBold
                                                        horizontalAlignment: Text.AlignHCenter
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    SurfaceCard {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 58
                                        radius: 18

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 12
                                            spacing: 10

                                            Text {
                                                text: root.glyph("info")
                                                color: colors.primary
                                                font.family: backend.materialFontFamily
                                                font.pixelSize: 18
                                            }

                                            Text {
                                                Layout.fillWidth: true
                                                text: backend.appearanceStatus
                                                color: colors.textMuted
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 9
                                                wrapMode: Text.WordWrap
                                            }
                                        }
                                    }
                                }
                            }

                            ColumnLayout {
                                spacing: 10

                                SurfaceCard {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 176
                                    radius: 22

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 9

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 10

                                            Rectangle {
                                                Layout.preferredWidth: 38
                                                Layout.preferredHeight: 38
                                                radius: 13
                                                color: colors.accentSoft

                                                Text {
                                                    anchors.centerIn: parent
                                                    text: root.glyph("home")
                                                    color: colors.primary
                                                    font.family: backend.materialFontFamily
                                                    font.pixelSize: 20
                                                }
                                            }

                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 1

                                                Text {
                                                    text: "Home Assistant"
                                                    color: colors.text
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 13
                                                    font.weight: Font.DemiBold
                                                }

                                                Text {
                                                    text: "Connect and pin up to five entities"
                                                    color: colors.textMuted
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 9
                                                }
                                            }
                                        }

                                        TextField {
                                            id: haUrlField

                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 42
                                            placeholderText: "https://homeassistant.local:8123"
                                            text: backend.haUrl
                                            color: colors.text
                                            placeholderTextColor: colors.inactive
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 10
                                            leftPadding: 13
                                            rightPadding: 13
                                            selectByMouse: true
                                            onTextEdited: backend.setHomeAssistantUrl(text)

                                            background: Rectangle {
                                                radius: 14
                                                color: colors.cardStrongBg
                                                border.width: haUrlField.activeFocus ? 2 : 1
                                                border.color: haUrlField.activeFocus
                                                              ? colors.primary
                                                              : colors.panelBorder
                                            }
                                        }

                                        TextField {
                                            id: haTokenField

                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 42
                                            placeholderText: "Long-lived access token"
                                            echoMode: TextInput.Password
                                            text: backend.haToken
                                            color: colors.text
                                            placeholderTextColor: colors.inactive
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 10
                                            leftPadding: 13
                                            rightPadding: 13
                                            selectByMouse: true
                                            onTextEdited: backend.setHomeAssistantToken(text)

                                            background: Rectangle {
                                                radius: 14
                                                color: colors.cardStrongBg
                                                border.width: haTokenField.activeFocus ? 2 : 1
                                                border.color: haTokenField.activeFocus
                                                              ? colors.primary
                                                              : colors.panelBorder
                                            }
                                        }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    ActionButton {
                                        Layout.fillWidth: true
                                        text: "Save connection"
                                        emphasized: true
                                        onClicked: backend.saveHomeAssistantSettings()
                                    }

                                    ActionButton {
                                        Layout.fillWidth: true
                                        text: "Fetch entities"
                                        onClicked: backend.refreshHomeAssistant()
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: backend.haSettingsStatus
                                    color: colors.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 9
                                    wrapMode: Text.WordWrap
                                }

                                SectionHeader {
                                    title: "Available entities"
                                    detail: "Pin to dashboard"
                                }

                                ListView {
                                    id: entitiesList

                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    clip: true
                                    spacing: 8
                                    model: backend.haEntities
                                    boundsBehavior: Flickable.StopAtBounds

                                    ScrollBar.vertical: ScrollBar {
                                        policy: ScrollBar.AsNeeded
                                        width: 4

                                        contentItem: Rectangle {
                                            implicitWidth: 4
                                            implicitHeight: 70
                                            radius: 2
                                            color: colors.primary
                                            opacity: 0.5
                                        }
                                    }

                                    delegate: SurfaceCard {
                                        id: entityCard

                                        required property var modelData

                                        width: ListView.view.width
                                        height: 68
                                        radius: 18

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 11
                                            spacing: 10

                                            Rectangle {
                                                Layout.preferredWidth: 36
                                                Layout.preferredHeight: 36
                                                radius: 12
                                                color: colors.cardStrongBg

                                                Text {
                                                    anchors.centerIn: parent
                                                    text: root.glyph("sensors")
                                                    color: colors.primary
                                                    font.family: backend.materialFontFamily
                                                    font.pixelSize: 17
                                                }
                                            }

                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 2

                                                Text {
                                                    Layout.fillWidth: true
                                                    text: entityCard.modelData.name
                                                    color: colors.text
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 10
                                                    font.weight: Font.DemiBold
                                                    elide: Text.ElideRight
                                                }

                                                Text {
                                                    Layout.fillWidth: true
                                                    text: entityCard.modelData.entity_id
                                                          + "  •  "
                                                          + entityCard.modelData.state
                                                    color: colors.textMuted
                                                    font.family: backend.monoFontFamily
                                                    font.pixelSize: 8
                                                    elide: Text.ElideRight
                                                }
                                            }

                                            ActionButton {
                                                text: entityCard.modelData.pinned ? "Unpin" : "Pin"
                                                emphasized: !entityCard.modelData.pinned
                                                onClicked: backend.togglePinEntity(
                                                               entityCard.modelData.entity_id)
                                            }
                                        }
                                    }

                                    footer: Item { height: 4 }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Shortcut {
        sequence: "Escape"
        onActivated: {
            if (mainStack.currentIndex === 1)
                mainStack.currentIndex = 0
            else
                backend.closeCenter()
        }
    }
}
