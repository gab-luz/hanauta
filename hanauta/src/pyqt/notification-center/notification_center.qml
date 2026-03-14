import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Window {
    id: root
    width: 430
    height: 900
    visible: true
    color: "transparent"
    title: "Hanauta Notification Center"
    flags: Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint

    property var colors: backend.palette
    property int settingsSection: 0
    property color mediaControlColor: Qt.rgba(1, 1, 1, 0.76)

    function glyph(name) {
        return backend.materialIcon(name)
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"

        Rectangle {
            id: panel
            width: parent.width - 22
            height: parent.height - 22
            anchors.centerIn: parent
            radius: 28
            color: colors.panelBg
            border.width: 1
            border.color: colors.panelBorder
            clip: true

            Rectangle {
                width: 240
                height: 240
                radius: 120
                x: -40
                y: -70
                color: colors.accentSoft
                opacity: 0.28
            }

            Rectangle {
                width: 180
                height: 180
                radius: 90
                anchors.right: parent.right
                anchors.rightMargin: -36
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 84
                color: colors.primary
                opacity: 0.10
            }

            StackLayout {
                id: stack
                anchors.fill: parent
                anchors.margins: 20
                currentIndex: 0

                ScrollView {
                    id: overviewView
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    ScrollBar.vertical: ScrollBar {
                        policy: ScrollBar.AsNeeded
                        width: 10
                        opacity: 0.0

                        contentItem: Rectangle {
                            implicitWidth: 10
                            implicitHeight: 80
                            radius: 5
                            color: "transparent"
                        }

                        background: Rectangle {
                            color: "transparent"
                        }
                    }

                    contentWidth: availableWidth

                    ColumnLayout {
                        width: overviewView.availableWidth
                        spacing: 12

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 14

                            Rectangle {
                                width: 48
                                height: 48
                                radius: 24
                                gradient: Gradient {
                                    GradientStop { position: 0.0; color: colors.primary }
                                    GradientStop { position: 1.0; color: colors.tertiary }
                                }

                                Text {
                                    anchors.centerIn: parent
                                    text: glyph("person")
                                    font.family: backend.materialFontFamily
                                    font.pixelSize: 24
                                    color: colors.onPrimary
                                }
                            }

                            ColumnLayout {
                                spacing: 2

                                Text {
                                    text: backend.username
                                    color: colors.text
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 18
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    text: "up " + backend.uptime
                                    color: colors.textMuted
                                    font.family: backend.monoFontFamily
                                    font.pixelSize: 10
                                }
                            }

                            Item { Layout.fillWidth: true }

                            RoundButton {
                                text: root.glyph("settings")
                                font.family: backend.materialFontFamily
                                font.pixelSize: 18
                                palette.buttonText: colors.icon
                                onClicked: stack.currentIndex = 1

                                background: Rectangle {
                                    radius: width / 2
                                    color: parent.hovered ? colors.hoverBg : colors.cardStrongBg
                                }
                            }

                            RoundButton {
                                text: root.glyph("power_settings_new")
                                font.family: backend.materialFontFamily
                                font.pixelSize: 18
                                palette.buttonText: colors.dangerFg
                                onClicked: backend.closeCenter()

                                background: Rectangle {
                                    radius: width / 2
                                    color: colors.dangerBg
                                }
                            }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            rowSpacing: 10
                            columnSpacing: 10

                            Repeater {
                                model: backend.quickSettings

                                delegate: Rectangle {
                                    required property var modelData
                                    required property int index
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 78
                                    radius: 20
                                    color: modelData.active ? colors.primary : colors.cardBg
                                    border.width: 1
                                    border.color: modelData.active ? colors.primary : colors.panelBorder
                                    scale: tileMouse.containsMouse ? 1.015 : 1.0

                                    Behavior on scale {
                                        NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
                                    }

                                    MouseArea {
                                        id: tileMouse
                                        anchors.fill: parent
                                        onClicked: backend.toggleQuickSetting(parent.modelData.key)
                                        hoverEnabled: true
                                    }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 10

                                        Text {
                                            text: root.glyph(modelData.icon)
                                            font.family: backend.materialFontFamily
                                            font.pixelSize: 20
                                            color: modelData.active ? colors.onPrimary : colors.icon
                                        }

                                        ColumnLayout {
                                            spacing: 2
                                            Layout.fillWidth: true

                                            Text {
                                                text: modelData.title
                                                color: modelData.active ? colors.onPrimary : colors.text
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 12
                                                font.weight: Font.DemiBold
                                            }

                                            Text {
                                                text: modelData.subtitle
                                                color: modelData.active ? colors.onPrimary : colors.textMuted
                                                opacity: modelData.active ? 0.75 : 1.0
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

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 48
                                radius: 24
                                color: colors.cardBg

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 14
                                    spacing: 12

                                    Text {
                                        text: root.glyph("brightness_medium")
                                        font.family: backend.materialFontFamily
                                        font.pixelSize: 20
                                        color: colors.primary
                                    }

                                    Slider {
                                        Layout.fillWidth: true
                                        from: 0
                                        to: 100
                                        value: backend.brightness
                                        live: true
                                        onValueChanged: if (pressed) backend.setBrightness(Math.round(value))

                                        background: Rectangle {
                                            x: 0
                                            y: (parent.height - height) / 2
                                            width: parent.width
                                            height: 42
                                            radius: 21
                                            color: colors.cardStrongBg

                                            Rectangle {
                                                width: parent.width * (parent.parent.visualPosition || 0)
                                                height: parent.height
                                                radius: 21
                                                color: colors.primary
                                            }
                                        }

                                        handle: Rectangle {
                                            implicitWidth: 18
                                            implicitHeight: 18
                                            radius: 9
                                            color: "transparent"
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 48
                                radius: 24
                                color: colors.cardBg

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 14
                                    spacing: 12

                                    Text {
                                        text: root.glyph("volume_up")
                                        font.family: backend.materialFontFamily
                                        font.pixelSize: 20
                                        color: colors.primary
                                    }

                                    Slider {
                                        Layout.fillWidth: true
                                        from: 0
                                        to: 100
                                        value: backend.volume
                                        live: true
                                        onValueChanged: if (pressed) backend.setVolume(Math.round(value))

                                        background: Rectangle {
                                            x: 0
                                            y: (parent.height - height) / 2
                                            width: parent.width
                                            height: 42
                                            radius: 21
                                            color: colors.cardStrongBg

                                            Rectangle {
                                                width: parent.width * (parent.parent.visualPosition || 0)
                                                height: parent.height
                                                radius: 21
                                                color: colors.primary
                                            }
                                        }

                                        handle: Rectangle {
                                            implicitWidth: 18
                                            implicitHeight: 18
                                            radius: 9
                                            color: "transparent"
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 168
                            radius: 22
                            border.width: 1
                            border.color: colors.mediaBorder
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: colors.mediaStart }
                                GradientStop { position: 0.55; color: colors.mediaEnd }
                                GradientStop { position: 1.0; color: colors.panelBg }
                            }

                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: 1
                                radius: parent.radius - 1
                                color: "#7F000000"
                            }

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 12

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 14

                                    Rectangle {
                                        width: 62
                                        height: 62
                                        radius: 16
                                        color: colors.cardStrongBg
                                        border.width: 1
                                        border.color: colors.panelBorder
                                        clip: true

                                        Image {
                                            anchors.fill: parent
                                            source: backend.mediaCover
                                            fillMode: Image.PreserveAspectCrop
                                            visible: source !== ""
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2

                                        Text {
                                            text: backend.mediaTitle
                                            color: colors.text
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 15
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }

                                        Text {
                                            text: backend.mediaArtist
                                            color: colors.primary
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 12
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 4
                                    radius: 2
                                    color: colors.panelBorder

                                    Rectangle {
                                        width: parent.width * backend.mediaProgress
                                        height: parent.height
                                        radius: 2
                                        color: colors.primary
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true

                                    Text {
                                        text: backend.mediaElapsed
                                        color: colors.inactive
                                        font.family: backend.monoFontFamily
                                        font.pixelSize: 10
                                    }

                                    Item { Layout.fillWidth: true }

                                    RoundButton {
                                        text: root.glyph("skip_previous")
                                        font.family: backend.materialFontFamily
                                        font.pixelSize: 20
                                        palette.buttonText: root.mediaControlColor
                                        onClicked: backend.triggerMediaAction("previous")
                                        background: Rectangle { color: "transparent"; radius: width / 2 }
                                    }

                                    RoundButton {
                                        text: backend.mediaStatus === "Playing" ? root.glyph("pause") : root.glyph("play_arrow")
                                        font.family: backend.materialFontFamily
                                        font.pixelSize: 20
                                        onClicked: backend.triggerMediaAction("toggle")
                                        palette.buttonText: colors.playFg
                                        background: Rectangle { color: colors.primary; radius: width / 2 }
                                    }

                                    RoundButton {
                                        text: root.glyph("skip_next")
                                        font.family: backend.materialFontFamily
                                        font.pixelSize: 20
                                        palette.buttonText: root.mediaControlColor
                                        onClicked: backend.triggerMediaAction("next")
                                        background: Rectangle { color: "transparent"; radius: width / 2 }
                                    }

                                    Item { Layout.fillWidth: true }

                                    Text {
                                        text: backend.mediaTotal
                                        color: colors.inactive
                                        font.family: backend.monoFontFamily
                                        font.pixelSize: 10
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 64
                            radius: 20
                            color: colors.cardBg
                            border.width: 1
                            border.color: colors.panelBorder

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 8

                                Image {
                                    source: "../../assets/kdeconnect.svg"
                                    sourceSize.width: 18
                                    sourceSize.height: 18
                                    fillMode: Image.PreserveAspectFit
                                    Layout.preferredWidth: 18
                                    Layout.preferredHeight: 18
                                }

                                Text {
                                    text: backend.phoneInfo.name || "No devices connected"
                                    color: colors.text
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    Layout.fillWidth: true
                                }

                                Text {
                                    text: backend.phoneInfo.status || ""
                                    color: colors.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                }

                                Text {
                                    text: backend.phoneInfo.battery || ""
                                    color: colors.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                }

                                Rectangle {
                                    width: 10
                                    height: 10
                                    radius: 5
                                    color: backend.phoneInfo.online ? colors.phoneOnline : colors.phoneOffline
                                }
                            }
                        }

                        Rectangle {
                            visible: backend.homeAssistantVisible
                            Layout.fillWidth: true
                            Layout.preferredHeight: 118
                            radius: 20
                            color: colors.cardBg
                            border.width: 1
                            border.color: colors.panelBorder

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 8

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    Image {
                                        source: "../../assets/home-assistant-dark.svg"
                                        sourceSize.width: 18
                                        sourceSize.height: 18
                                        fillMode: Image.PreserveAspectFit
                                        Layout.preferredWidth: 18
                                        Layout.preferredHeight: 18
                                    }

                                    Text {
                                        text: backend.homeAssistantStatus
                                        color: colors.textMuted
                                        font.family: backend.uiFontFamily
                                        font.pixelSize: 10
                                        Layout.fillWidth: true
                                        elide: Text.ElideRight
                                    }

                                    Button {
                                        text: "Settings"
                                        onClicked: backend.openSettingsApp("services")
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6

                                    Repeater {
                                        model: backend.homeAssistantTiles

                                        delegate: Rectangle {
                                            required property var modelData
                                            required property int index
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 72
                                            radius: 16
                                            color: colors.cardStrongBg
                                            border.width: 1
                                            border.color: colors.panelBorder

                                            MouseArea {
                                                anchors.fill: parent
                                                enabled: parent.modelData.enabled
                                                onClicked: backend.activateHomeAssistantTile(index)
                                            }

                                            Column {
                                                anchors.centerIn: parent
                                                spacing: 4

                                                Text {
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    text: root.glyph(modelData.icon)
                                                    font.family: backend.materialFontFamily
                                                    font.pixelSize: 18
                                                    color: colors.primary
                                                }

                                                Text {
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    text: modelData.title
                                                    color: colors.text
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 10
                                                    font.weight: Font.DemiBold
                                                }

                                                Text {
                                                    anchors.horizontalCenter: parent.horizontalCenter
                                                    text: modelData.subtitle
                                                    color: colors.textMuted
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 9
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Repeater {
                            model: backend.serviceCards

                            delegate: Rectangle {
                                required property var modelData
                                required property int index
                                Layout.fillWidth: true
                                Layout.preferredHeight: 72
                                radius: 20
                                color: colors.cardBg
                                border.width: 1
                                border.color: colors.panelBorder

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 10

                                    Text {
                                        text: root.glyph(modelData.icon)
                                        font.family: backend.materialFontFamily
                                        font.pixelSize: 18
                                        color: colors.primary
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 2

                                        Text {
                                            text: modelData.title
                                            color: colors.text
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 12
                                            font.weight: Font.DemiBold
                                        }

                                        Text {
                                            text: modelData.detail
                                            color: colors.textMuted
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 10
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                        }
                                    }

                                    Button {
                                        text: "Open"
                                        onClicked: backend.launchService(modelData.key)
                                    }
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    spacing: 16

                    Rectangle {
                        Layout.preferredWidth: 150
                        Layout.fillHeight: true
                        radius: 22
                        color: colors.cardBg
                        border.width: 1
                        border.color: colors.panelBorder

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 10

                            RowLayout {
                                Layout.fillWidth: true

                                RoundButton {
                                    text: root.glyph("arrow_back")
                                    font.family: backend.materialFontFamily
                                    onClicked: stack.currentIndex = 0
                                    background: Rectangle { radius: width / 2; color: colors.cardStrongBg }
                                }

                                Text {
                                    text: "Settings"
                                    color: colors.text
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 15
                                    font.weight: Font.DemiBold
                                }
                            }

                            Repeater {
                                model: [
                                    { title: "Overview", icon: "hub" },
                                    { title: "Appearance", icon: "invert_colors" },
                                    { title: "Home Assistant", icon: "home" }
                                ]

                                delegate: Rectangle {
                                    required property var modelData
                                    required property int index
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 48
                                    radius: 16
                                    color: index === settingsSection ? colors.primary : colors.cardStrongBg

                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: settingsSection = index
                                    }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 10

                                        Text {
                                            text: root.glyph(modelData.icon)
                                            font.family: backend.materialFontFamily
                                            font.pixelSize: 18
                                            color: index === settingsSection ? colors.onPrimary : colors.icon
                                        }

                                        Text {
                                            text: modelData.title
                                            color: index === settingsSection ? colors.onPrimary : colors.text
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 12
                                            font.weight: Font.DemiBold
                                        }
                                    }
                                }
                            }

                            Item { Layout.fillHeight: true }

                            Button {
                                Layout.fillWidth: true
                                text: "Open Full Settings"
                                onClicked: backend.openOverviewSettings()
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        radius: 22
                        color: colors.cardBg
                        border.width: 1
                        border.color: colors.panelBorder

                        StackLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            currentIndex: settingsSection

                            ColumnLayout {
                                spacing: 12

                                Text {
                                    text: "System Overview"
                                    color: colors.text
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 16
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    text: "Quick telemetry for this session and shell environment."
                                    color: colors.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                }

                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: 2
                                    rowSpacing: 10
                                    columnSpacing: 10

                                    Repeater {
                                        model: backend.systemOverview

                                        delegate: Rectangle {
                                            required property var modelData
                                            required property int index
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 78
                                            radius: 16
                                            color: colors.cardStrongBg
                                            border.width: 1
                                            border.color: colors.panelBorder

                                            Column {
                                                anchors.fill: parent
                                                anchors.margins: 12
                                                spacing: 4

                                                Text {
                                                    text: modelData.label
                                                    color: colors.inactive
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 10
                                                }

                                                Text {
                                                    text: modelData.value
                                                    color: colors.text
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 12
                                                    font.weight: Font.DemiBold
                                                    wrapMode: Text.WordWrap
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            ColumnLayout {
                                spacing: 12

                                Text {
                                    text: "Appearance"
                                    color: colors.text
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 16
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    text: "Pick an accent preset for the notification center."
                                    color: colors.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                }

                                Text {
                                    text: backend.appearanceStatus
                                    color: colors.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                }

                                RowLayout {
                                    spacing: 10

                                    Repeater {
                                        model: ["orchid", "mint", "sunset"]

                                        delegate: Button {
                                            required property string modelData
                                            text: modelData.charAt(0).toUpperCase() + modelData.slice(1)
                                            onClicked: backend.setAccent(modelData)
                                        }
                                    }
                                }
                            }

                            ColumnLayout {
                                spacing: 12

                                Text {
                                    text: "Home Assistant"
                                    color: colors.text
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 16
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    text: "Connect to your instance, browse entities, and pin up to five controls."
                                    color: colors.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }

                                TextField {
                                    Layout.fillWidth: true
                                    placeholderText: "https://homeassistant.local:8123"
                                    text: backend.haUrl
                                    onTextChanged: backend.setHomeAssistantUrl(text)
                                }

                                TextField {
                                    Layout.fillWidth: true
                                    placeholderText: "Long-lived access token"
                                    echoMode: TextInput.Password
                                    text: backend.haToken
                                    onTextChanged: backend.setHomeAssistantToken(text)
                                }

                                RowLayout {
                                    spacing: 8

                                    Button {
                                        text: "Save"
                                        onClicked: backend.saveHomeAssistantSettings()
                                    }

                                    Button {
                                        text: "Fetch Entities"
                                        onClicked: backend.refreshHomeAssistant()
                                    }
                                }

                                Text {
                                    text: backend.haSettingsStatus
                                    color: colors.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                }

                                ListView {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    clip: true
                                    spacing: 8
                                    model: backend.haEntities

                                    delegate: Rectangle {
                                        required property var modelData
                                        width: ListView.view.width
                                        height: 72
                                        radius: 16
                                        color: colors.cardStrongBg
                                        border.width: 1
                                        border.color: colors.panelBorder

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 12
                                            spacing: 10

                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 2

                                                Text {
                                                    text: parent.modelData.name
                                                    color: colors.text
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 12
                                                    font.weight: Font.DemiBold
                                                    elide: Text.ElideRight
                                                    Layout.fillWidth: true
                                                }

                                                Text {
                                                    text: parent.modelData.entity_id + " • " + parent.modelData.state
                                                    color: colors.textMuted
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 10
                                                    elide: Text.ElideRight
                                                    Layout.fillWidth: true
                                                }
                                            }

                                            Button {
                                                text: parent.modelData.pinned ? "Unpin" : "Pin"
                                                onClicked: backend.togglePinEntity(parent.parent.modelData.entity_id)
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
        sequence: "Escape"
        onActivated: backend.closeCenter()
    }
}
