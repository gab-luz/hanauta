import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Effects

Window {
    id: root

    width: backend.ncWidth
    height: backend.ncHeight
    visible: true
    color: "transparent"
    title: "Hanauta Notification Center"
    flags: Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint

    property int settingsSection: 0

    QtObject {
        id: colors

        property color panelBg: backend.palettePanelBg
        property color panelBorder: backend.palettePanelBorder
        property color cardBg: backend.paletteCardBg
        property color cardStrongBg: backend.paletteCardStrongBg
        property color hoverBg: backend.paletteHoverBg
        property color accentSoft: backend.paletteAccentSoft
        property color primary: backend.palettePrimary
        property color tertiary: backend.paletteTertiary
        property color secondary: backend.paletteSecondary
        property color onSecondary: backend.paletteOnSecondary
        property color onPrimary: backend.paletteOnPrimary
        property color text: backend.paletteText
        property color textMuted: backend.paletteTextMuted
        property color icon: backend.paletteIcon
        property color inactive: backend.paletteInactive
        property color dangerFg: backend.paletteDangerFg
        property color dangerBg: backend.paletteDangerBg
        property color playFg: backend.palettePlayFg
        property color mediaStart: backend.paletteMediaStart
        property color mediaEnd: backend.paletteMediaEnd
        property color mediaBorder: backend.paletteMediaBorder
        property color phoneOnline: backend.palettePhoneOnline
        property color phoneOffline: backend.palettePhoneOffline
    }

    property color panelColor: colors.panelBg
    property color onPrimaryColor: colors.onPrimary
    property color secondaryColor: colors.secondary
    property color onSecondaryColor: colors.onSecondary

    function glyph(name) {
        return backend.materialIcon(name)
    }

    function clamp(value, minimum, maximum) {
        return Math.max(minimum, Math.min(maximum, value))
    }

    function quickLabel(key, title) {
        if (key === "dnd")
            return "DND"
        if (key === "airplane")
            return "Airplane"
        return title
    }

    component IconButton: RoundButton {
        id: iconButton

        property string iconName: ""
        property color foreground: colors.icon
        property color restingColor: Qt.rgba(1, 1, 1, 0.05)
        property color hoverColor: Qt.rgba(1, 1, 1, 0.10)

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
            border.color: Qt.rgba(1, 1, 1, 0.06)

            Behavior on color {
                ColorAnimation { duration: 120 }
            }
        }

        scale: down ? 0.92 : 1.0

        Behavior on scale {
            NumberAnimation { duration: 90; easing.type: Easing.OutCubic }
        }
    }

    component ActionButton: Button {
        id: actionButton

        property bool emphasized: false

        implicitHeight: 38
        leftPadding: 16
        rightPadding: 16
        hoverEnabled: true

        contentItem: Text {
            text: actionButton.text
            color: actionButton.emphasized
                   ? root.onPrimaryColor
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
            color: actionButton.emphasized
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
        radius: 20
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
            font.pixelSize: 12
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

    component QuickTile: Rectangle {
        id: quickTile

        required property var modelData
        required property int index

        property string key: String(modelData.key)
        property string iconName: String(modelData.icon)
        property string title: root.quickLabel(key, String(modelData.title))
        property string subtitle: String(modelData.subtitle)
        property bool active: Boolean(modelData.active)
        property color activeColor: colors.primary
        property color activeTextColor: root.onPrimaryColor

        Layout.fillWidth: true
        Layout.preferredHeight: 62
        radius: 16
        border.width: 1
        color: active
               ? activeColor
               : tileMouse.containsMouse
                 ? Qt.rgba(1, 1, 1, 0.10)
                 : Qt.rgba(1, 1, 1, 0.05)
        border.color: active
                      ? Qt.rgba(activeColor.r, activeColor.g, activeColor.b, 0.55)
                      : Qt.rgba(1, 1, 1, 0.06)
        scale: tileMouse.pressed
               ? 0.95
               : tileMouse.containsMouse
                 ? 1.02
                 : 1.0

        Behavior on color {
            ColorAnimation { duration: 140 }
        }

        Behavior on scale {
            NumberAnimation { duration: 110; easing.type: Easing.OutCubic }
        }

        MouseArea {
            id: tileMouse

            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: backend.toggleQuickSetting(quickTile.key)
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 12
            spacing: 12

            Text {
                text: root.glyph(quickTile.iconName)
                color: quickTile.active
                       ? quickTile.activeTextColor
                       : Qt.rgba(1, 1, 1, 0.72)
                font.family: backend.materialFontFamily
                font.pixelSize: 22
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 1

                Text {
                    Layout.fillWidth: true
                    text: quickTile.title
                    color: quickTile.active
                           ? quickTile.activeTextColor
                           : "#FFFFFF"
                    font.family: backend.uiFontFamily
                    font.pixelSize: 12
                    font.weight: Font.Bold
                    elide: Text.ElideRight
                }

                Text {
                    Layout.fillWidth: true
                    text: quickTile.subtitle
                    color: quickTile.active
                           ? Qt.rgba(quickTile.activeTextColor.r,
                                     quickTile.activeTextColor.g,
                                     quickTile.activeTextColor.b,
                                     0.72)
                           : Qt.rgba(1, 1, 1, 0.50)
                    font.family: backend.uiFontFamily
                    font.pixelSize: 10
                    elide: Text.ElideRight
                }
            }
        }
    }

    component PillSlider: Rectangle {
        id: pillSlider

        property string iconName: ""
        property real sliderValue: 0
        signal edited(real value)

        Layout.fillWidth: true
        Layout.preferredHeight: 44
        radius: height / 2
        color: Qt.rgba(1, 1, 1, 0.05)

        Rectangle {
            id: sliderFill

            width: Math.max(56, pillSlider.width * (pillSlider.sliderValue / 100))
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            radius: height / 2
            color: colors.primary

            Behavior on width {
                NumberAnimation { duration: 90 }
            }
        }

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            text: root.glyph(pillSlider.iconName)
            color: root.onPrimaryColor
            font.family: backend.materialFontFamily
            font.pixelSize: 20
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: pillSlider.edited(
                           root.clamp(Math.round(mouse.x / width * 100), 0, 100))
            onPositionChanged: if (pressed)
                                   pillSlider.edited(
                                       root.clamp(Math.round(mouse.x / width * 100), 0, 100))
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
            radius: 24
            color: Qt.rgba(panelColor.r, panelColor.g, panelColor.b, 0.65)
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.08)
            clip: true
            opacity: 0
            scale: 0.97

            layer.enabled: true
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: "black"
                shadowOpacity: 0.42
                shadowBlur: 0.6
                shadowVerticalOffset: 8
                shadowHorizontalOffset: 0
            }

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
                    from: 0.97
                    to: 1
                    duration: 240
                    easing.type: Easing.OutBack
                    easing.overshoot: 0.75
                }
            }

            StackLayout {
                id: mainStack

                anchors.fill: parent
                currentIndex: 0

                Item {
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 24
                        anchors.rightMargin: 24
                        anchors.topMargin: 22
                        anchors.bottomMargin: 22
                        spacing: 18

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 48
                            spacing: 14

                            Rectangle {
                                Layout.preferredWidth: 48
                                Layout.preferredHeight: 48
                                radius: 24
                                gradient: Gradient {
                                    GradientStop { position: 0.0; color: colors.primary }
                                    GradientStop { position: 1.0; color: colors.tertiary }
                                }

                                Text {
                                    anchors.centerIn: parent
                                    text: root.glyph("person")
                                    color: root.onPrimaryColor
                                    font.family: backend.materialFontFamily
                                    font.pixelSize: 24
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 1

                                Text {
                                    Layout.fillWidth: true
                                    text: backend.username
                                    color: "#FFFFFF"
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 15
                                    font.weight: Font.Bold
                                    elide: Text.ElideRight
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: "up " + backend.uptime
                                    color: Qt.rgba(1, 1, 1, 0.50)
                                    font.family: backend.monoFontFamily
                                    font.pixelSize: 10
                                }
                            }

                            Item { Layout.fillWidth: true }

                            IconButton {
                                iconName: "settings"
                                onClicked: mainStack.currentIndex = 1
                            }

                            IconButton {
                                iconName: "power_settings_new"
                                foreground: "#F87171"
                                restingColor: Qt.rgba(239, 68, 68, 0.20)
                                hoverColor: Qt.rgba(239, 68, 68, 0.30)
                                onClicked: backend.closeCenter()
                            }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 10
                            rowSpacing: 10

                            Repeater {
                                model: backend.quickSettings

                                delegate: QuickTile {
                                    Layout.fillWidth: true
                                    activeColor: modelData.key === "night"
                                                 ? root.secondaryColor
                                                 : colors.primary
                                    activeTextColor: modelData.key === "night"
                                                     ? root.onSecondaryColor
                                                     : root.onPrimaryColor
                                }
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            PillSlider {
                                iconName: "brightness_medium"
                                sliderValue: backend.brightness
                                onEdited: value => backend.setBrightness(Math.round(value))
                            }

                            PillSlider {
                                iconName: backend.volume <= 0
                                          ? "volume_off"
                                          : backend.volume < 45
                                            ? "volume_down"
                                            : "volume_up"
                                sliderValue: backend.volume
                                onEdited: value => backend.setVolume(Math.round(value))
                            }
                        }

                        Item { Layout.fillHeight: true }

                        Rectangle {
                            id: mediaCard

                            Layout.fillWidth: true
                            Layout.preferredHeight: 160
                            radius: 16
                            color: Qt.rgba(73, 69, 79, 0.40)
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.05)

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 12

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 14

                                    Rectangle {
                                        Layout.preferredWidth: 56
                                        Layout.preferredHeight: 56
                                        radius: 12
                                        clip: true
                                        color: "#1F2937"
                                        border.width: 1
                                        border.color: Qt.rgba(1, 1, 1, 0.10)

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
                                            font.pixelSize: 26
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.fillHeight: true
                                        spacing: 3

                                        Text {
                                            Layout.fillWidth: true
                                            text: backend.mediaTitle || "Nothing playing"
                                            color: "#FFFFFF"
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 14
                                            font.weight: Font.Bold
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            text: backend.mediaArtist || "Start audio in any MPRIS player"
                                            color: colors.primary
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 12
                                            elide: Text.ElideRight
                                        }
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 4
                                    radius: 2
                                    color: Qt.rgba(1, 1, 1, 0.10)

                                    Rectangle {
                                        width: parent.width
                                               * root.clamp(backend.mediaProgress || 0, 0, 1)
                                        height: parent.height
                                        radius: parent.radius
                                        color: colors.primary

                                        Behavior on width {
                                            NumberAnimation { duration: 200 }
                                        }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Text {
                                        text: backend.mediaElapsed
                                        color: Qt.rgba(1, 1, 1, 0.50)
                                        font.family: backend.monoFontFamily
                                        font.pixelSize: 10
                                    }

                                    Item { Layout.fillWidth: true }

                                    IconButton {
                                        implicitWidth: 34
                                        implicitHeight: 34
                                        iconName: "skip_previous"
                                        foreground: Qt.rgba(1, 1, 1, 0.72)
                                        restingColor: "transparent"
                                        hoverColor: Qt.rgba(1, 1, 1, 0.10)
                                        onClicked: backend.triggerMediaAction("previous")
                                    }

                                    IconButton {
                                        implicitWidth: 42
                                        implicitHeight: 42
                                        iconName: backend.mediaStatus === "Playing"
                                                  ? "pause"
                                                  : "play_arrow"
                                        foreground: colors.onPrimary
                                        restingColor: colors.primary
                                        hoverColor: colors.primary
                                        onClicked: backend.triggerMediaAction("toggle")
                                    }

                                    IconButton {
                                        implicitWidth: 34
                                        implicitHeight: 34
                                        iconName: "skip_next"
                                        foreground: Qt.rgba(1, 1, 1, 0.72)
                                        restingColor: "transparent"
                                        hoverColor: Qt.rgba(1, 1, 1, 0.10)
                                        onClicked: backend.triggerMediaAction("next")
                                    }

                                    Item { Layout.fillWidth: true }

                                    Text {
                                        text: backend.mediaTotal
                                        color: Qt.rgba(1, 1, 1, 0.50)
                                        font.family: backend.monoFontFamily
                                        font.pixelSize: 10
                                    }
                                }
                            }
                        }
                    }
                }

                Item {
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 20
                        anchors.rightMargin: 20
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
                                    font.pixelSize: 16
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

                                ScrollBar.vertical: ScrollBar {
                                    policy: ScrollBar.AsNeeded
                                    width: 4
                                    opacity: 0.0

                                    contentItem: Rectangle {
                                        implicitWidth: 4
                                        implicitHeight: 72
                                        radius: 2
                                        color: colors.primary
                                    }

                                    background: Rectangle { color: "transparent" }
                                }

                                ColumnLayout {
                                    width: systemOverviewView.availableWidth
                                    spacing: 12

                                    SurfaceCard {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 88
                                        radius: 20

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 14
                                            spacing: 12

                                            Rectangle {
                                                Layout.preferredWidth: 50
                                                Layout.preferredHeight: 50
                                                radius: 16
                                                gradient: Gradient {
                                                    GradientStop { position: 0.0; color: colors.primary }
                                                    GradientStop { position: 1.0; color: colors.tertiary }
                                                }

                                                Text {
                                                    anchors.centerIn: parent
                                                    text: root.glyph("computer")
                                                    color: colors.onPrimary
                                                    font.family: backend.materialFontFamily
                                                    font.pixelSize: 24
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
                                                Layout.preferredHeight: 82
                                                radius: 18

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

                                ScrollBar.vertical: ScrollBar {
                                    policy: ScrollBar.AsNeeded
                                    width: 4
                                    opacity: 0.0

                                    contentItem: Rectangle {
                                        implicitWidth: 4
                                        implicitHeight: 72
                                        radius: 2
                                        color: colors.primary
                                    }

                                    background: Rectangle { color: "transparent" }
                                }

                                ColumnLayout {
                                    width: appearanceView.availableWidth
                                    spacing: 12

                                    SurfaceCard {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 150
                                        radius: 22
                                        clip: true

                                        Rectangle {
                                            width: 150
                                            height: 150
                                            radius: width / 2
                                            x: -56
                                            y: -64
                                            color: colors.accentSoft
                                            opacity: 0.55
                                        }

                                        Rectangle {
                                            width: 110
                                            height: 110
                                            radius: width / 2
                                            anchors.right: parent.right
                                            anchors.rightMargin: -40
                                            anchors.bottom: parent.bottom
                                            anchors.bottomMargin: -24
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
                                                    Layout.preferredWidth: 40
                                                    Layout.preferredHeight: 40
                                                    radius: 14
                                                    color: colors.primary
                                                }

                                                Rectangle {
                                                    Layout.preferredWidth: 40
                                                    Layout.preferredHeight: 40
                                                    radius: 14
                                                    color: colors.tertiary
                                                }

                                                Rectangle {
                                                    Layout.preferredWidth: 40
                                                    Layout.preferredHeight: 40
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
                                                Layout.preferredHeight: 82
                                                radius: 18
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
                                        Layout.preferredHeight: 54
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

                            ScrollView {
                                id: homeView

                                clip: true
                                contentWidth: availableWidth
                                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                                ScrollBar.vertical: ScrollBar {
                                    policy: ScrollBar.AsNeeded
                                    width: 4
                                    opacity: 0.0

                                    contentItem: Rectangle {
                                        implicitWidth: 4
                                        implicitHeight: 72
                                        radius: 2
                                        color: colors.primary
                                    }

                                    background: Rectangle { color: "transparent" }
                                }

                                ColumnLayout {
                                    width: homeView.availableWidth
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
                                        Layout.preferredHeight: 260
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
                                            height: 64
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
