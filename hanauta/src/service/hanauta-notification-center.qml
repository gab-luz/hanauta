import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Window {
    id: root
    width: 420
    height: 940
    visible: true
    color: "transparent"
    title: "Hanauta Notification Center"
    flags: Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint

    property var colors: backend.palette
    property int pageIndex: 0
    property string settingsSection: "overview"

    function glyph(name) {
        return backend.materialIcon(name)
    }

    function showSettings(section) {
        settingsSection = section || "overview"
        pageIndex = 1
    }

    function showOverview() {
        pageIndex = 0
    }

    Component.onCompleted: backend.refreshAll()

    Rectangle {
        anchors.fill: parent
        color: "transparent"

        Rectangle {
            anchors.fill: parent
            anchors.margins: 12
            radius: 32
            color: colors.panelBg
            border.width: 1
            border.color: colors.panelBorder

            StackLayout {
                anchors.fill: parent
                anchors.margins: 18
                currentIndex: pageIndex

                ScrollView {
                    clip: true
                    ScrollBar.vertical.policy: ScrollBar.AlwaysOff

                    ColumnLayout {
                        width: parent.width
                        spacing: 10

                        Rectangle {
                            Layout.fillWidth: true
                            radius: 24
                            color: colors.cardBg
                            border.width: 1
                            border.color: colors.panelBorder

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 12

                                Rectangle {
                                    Layout.preferredWidth: 46
                                    Layout.preferredHeight: 46
                                    radius: 16
                                    color: colors.primaryContainer

                                    Text {
                                        anchors.centerIn: parent
                                        text: glyph("person")
                                        color: colors.onPrimary
                                        font.family: backend.materialFontFamily
                                        font.pixelSize: 22
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2

                                    Text {
                                        text: backend.username
                                        color: colors.text
                                        font.family: backend.uiFontFamily
                                        font.pixelSize: 15
                                        font.weight: Font.DemiBold
                                    }

                                    Text {
                                        text: backend.uptime
                                        color: colors.textMuted
                                        font.family: backend.monoFontFamily
                                        font.pixelSize: 10
                                    }
                                }

                                ToolButton {
                                    text: glyph("settings")
                                    onClicked: showSettings("overview")
                                    background: Rectangle {
                                        radius: width / 2
                                        color: parent.hovered ? colors.hoverBg : "transparent"
                                    }
                                    contentItem: Text {
                                        text: parent.text
                                        color: colors.text
                                        font.family: backend.materialFontFamily
                                        font.pixelSize: 18
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                }

                                ToolButton {
                                    text: glyph("power_settings_new")
                                    onClicked: backend.closeCenter()
                                    background: Rectangle {
                                        radius: width / 2
                                        color: parent.hovered ? colors.dangerBg : "transparent"
                                    }
                                    contentItem: Text {
                                        text: parent.text
                                        color: colors.dangerFg
                                        font.family: backend.materialFontFamily
                                        font.pixelSize: 18
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                }
                            }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            columnSpacing: 10
                            rowSpacing: 10

                            Repeater {
                                model: backend.quickSettings

                                delegate: Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 84
                                    radius: 22
                                    color: modelData.active ? colors.primaryContainer : colors.cardStrongBg
                                    border.width: 1
                                    border.color: modelData.active ? colors.primary : colors.panelBorder

                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: backend.toggleQuickSetting(modelData.key)
                                    }

                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 6

                                        Text {
                                            text: glyph(modelData.icon)
                                            color: modelData.active ? colors.playFg : colors.text
                                            font.family: backend.materialFontFamily
                                            font.pixelSize: 22
                                        }

                                        Text {
                                            text: modelData.title
                                            color: modelData.active ? colors.playFg : colors.text
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 13
                                            font.weight: Font.DemiBold
                                        }

                                        Text {
                                            text: modelData.subtitle
                                            color: modelData.active ? colors.playFg : colors.textMuted
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 11
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            radius: 24
                            color: colors.cardBg
                            border.width: 1
                            border.color: colors.panelBorder

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 8

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10

                                    Text {
                                        text: glyph("brightness_medium")
                                        color: colors.text
                                        font.family: backend.materialFontFamily
                                        font.pixelSize: 18
                                    }

                                    Slider {
                                        Layout.fillWidth: true
                                        from: 0
                                        to: 100
                                        value: backend.brightness
                                        onMoved: backend.setBrightness(Math.round(value))
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 10

                                    Text {
                                        text: glyph("volume_up")
                                        color: colors.text
                                        font.family: backend.materialFontFamily
                                        font.pixelSize: 18
                                    }

                                    Slider {
                                        Layout.fillWidth: true
                                        from: 0
                                        to: 100
                                        value: backend.volume
                                        onMoved: backend.setVolume(Math.round(value))
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            radius: 26
                            color: colors.cardStrongBg
                            border.width: 1
                            border.color: colors.mediaBorder

                            Rectangle {
                                anchors.fill: parent
                                radius: parent.radius
                                gradient: Gradient {
                                    GradientStop { position: 0.0; color: colors.mediaStart }
                                    GradientStop { position: 1.0; color: colors.mediaEnd }
                                }
                                opacity: 0.88
                            }

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 12

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 12

                                    Rectangle {
                                        Layout.preferredWidth: 62
                                        Layout.preferredHeight: 62
                                        radius: 18
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
                                            font.pixelSize: 14
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            text: backend.mediaArtist
                                            color: colors.textMuted
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 12
                                            elide: Text.ElideRight
                                        }
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: 4
                                    radius: 2
                                    color: colors.cardBg

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
                                        color: colors.textMuted
                                        font.family: backend.monoFontFamily
                                        font.pixelSize: 10
                                    }

                                    Item { Layout.fillWidth: true }

                                    RowLayout {
                                        spacing: 10

                                        ToolButton {
                                            text: glyph("skip_previous")
                                            onClicked: backend.triggerMediaAction("previous")
                                            background: Rectangle {
                                                radius: width / 2
                                                color: parent.hovered ? colors.hoverBg : "transparent"
                                            }
                                            contentItem: Text {
                                                text: parent.text
                                                color: colors.text
                                                font.family: backend.materialFontFamily
                                                font.pixelSize: 20
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                        }

                                        ToolButton {
                                            text: backend.mediaStatus === "Playing" ? glyph("pause") : glyph("play_arrow")
                                            onClicked: backend.triggerMediaAction("toggle")
                                            background: Rectangle {
                                                radius: width / 2
                                                color: colors.primary
                                            }
                                            contentItem: Text {
                                                text: parent.text
                                                color: colors.playFg
                                                font.family: backend.materialFontFamily
                                                font.pixelSize: 22
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                        }

                                        ToolButton {
                                            text: glyph("skip_next")
                                            onClicked: backend.triggerMediaAction("next")
                                            background: Rectangle {
                                                radius: width / 2
                                                color: parent.hovered ? colors.hoverBg : "transparent"
                                            }
                                            contentItem: Text {
                                                text: parent.text
                                                color: colors.text
                                                font.family: backend.materialFontFamily
                                                font.pixelSize: 20
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                        }
                                    }

                                    Item { Layout.fillWidth: true }

                                    Text {
                                        text: backend.mediaTotal
                                        color: colors.textMuted
                                        font.family: backend.monoFontFamily
                                        font.pixelSize: 10
                                    }
                                }
                            }
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            radius: 22
                            color: colors.cardBg
                            border.width: 1
                            border.color: colors.panelBorder

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 10

                                Text {
                                    text: glyph("phone_android")
                                    color: colors.text
                                    font.family: backend.materialFontFamily
                                    font.pixelSize: 18
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: backend.phoneInfo.name || "No devices connected"
                                    color: colors.text
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
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
                            }
                        }

                        Rectangle {
                            visible: backend.homeAssistantVisible
                            Layout.fillWidth: true
                            radius: 22
                            color: colors.cardBg
                            border.width: 1
                            border.color: colors.panelBorder

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 10

                                RowLayout {
                                    Layout.fillWidth: true

                                    Text {
                                        text: glyph("home")
                                        color: colors.text
                                        font.family: backend.materialFontFamily
                                        font.pixelSize: 18
                                    }

                                    Text {
                                        text: "Home Assistant"
                                        color: colors.text
                                        font.family: backend.uiFontFamily
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                    }

                                    Item { Layout.fillWidth: true }

                                    ToolButton {
                                        text: glyph("settings")
                                        onClicked: showSettings("homeassistant")
                                        background: Rectangle {
                                            radius: width / 2
                                            color: parent.hovered ? colors.hoverBg : "transparent"
                                        }
                                        contentItem: Text {
                                            text: parent.text
                                            color: colors.text
                                            font.family: backend.materialFontFamily
                                            font.pixelSize: 18
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6

                                    Repeater {
                                        model: backend.homeAssistantTiles

                                        delegate: Rectangle {
                                            Layout.fillWidth: true
                                            Layout.preferredHeight: 76
                                            radius: 18
                                            color: modelData.enabled ? colors.cardStrongBg : colors.surfaceContainer
                                            border.width: 1
                                            border.color: modelData.enabled ? colors.primary : colors.panelBorder

                                            MouseArea {
                                                anchors.fill: parent
                                                enabled: modelData.enabled
                                                onClicked: backend.activateHomeAssistantTile(index)
                                            }

                                            Column {
                                                anchors.fill: parent
                                                anchors.margins: 10
                                                spacing: 4

                                                Text {
                                                    text: glyph(modelData.icon)
                                                    color: modelData.enabled ? colors.primary : colors.inactive
                                                    font.family: backend.materialFontFamily
                                                    font.pixelSize: 18
                                                }

                                                Text {
                                                    text: modelData.title
                                                    color: colors.text
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 11
                                                    font.weight: Font.DemiBold
                                                    elide: Text.ElideRight
                                                    width: parent.width
                                                }

                                                Text {
                                                    text: modelData.subtitle
                                                    color: colors.textMuted
                                                    font.family: backend.uiFontFamily
                                                    font.pixelSize: 10
                                                    elide: Text.ElideRight
                                                    width: parent.width
                                                }
                                            }
                                        }
                                    }
                                }

                                Text {
                                    text: backend.homeAssistantStatus
                                    color: colors.textMuted
                                    font.family: backend.uiFontFamily
                                    font.pixelSize: 11
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        Repeater {
                            model: backend.serviceCards

                            delegate: Rectangle {
                                Layout.fillWidth: true
                                radius: 22
                                color: colors.cardBg
                                border.width: 1
                                border.color: colors.panelBorder

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 14
                                    spacing: 12

                                    Rectangle {
                                        Layout.preferredWidth: 44
                                        Layout.preferredHeight: 44
                                        radius: 16
                                        color: colors.cardStrongBg

                                        Text {
                                            anchors.centerIn: parent
                                            text: glyph(modelData.icon)
                                            color: colors.primary
                                            font.family: backend.materialFontFamily
                                            font.pixelSize: 20
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 3

                                        Text {
                                            text: modelData.title
                                            color: colors.text
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 13
                                            font.weight: Font.DemiBold
                                        }

                                        Text {
                                            text: modelData.detail
                                            color: colors.textMuted
                                            font.family: backend.uiFontFamily
                                            font.pixelSize: 11
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

                Rectangle {
                    color: "transparent"

                    RowLayout {
                        anchors.fill: parent
                        spacing: 16

                        Rectangle {
                            Layout.preferredWidth: 132
                            Layout.fillHeight: true
                            radius: 24
                            color: colors.cardBg
                            border.width: 1
                            border.color: colors.panelBorder

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 8

                                RowLayout {
                                    Layout.fillWidth: true

                                    ToolButton {
                                        text: glyph("arrow_back")
                                        onClicked: showOverview()
                                        background: Rectangle {
                                            radius: width / 2
                                            color: parent.hovered ? colors.hoverBg : "transparent"
                                        }
                                        contentItem: Text {
                                            text: parent.text
                                            color: colors.text
                                            font.family: backend.materialFontFamily
                                            font.pixelSize: 18
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                        }
                                    }

                                    Text {
                                        text: "Settings"
                                        color: colors.text
                                        font.family: "Outfit"
                                        font.pixelSize: 18
                                        font.weight: Font.Medium
                                    }
                                }

                                Repeater {
                                    model: [
                                        { key: "overview", title: "Overview", icon: "hub" },
                                        { key: "appearance", title: "Appearance", icon: "invert_colors" },
                                        { key: "homeassistant", title: "Home Assistant", icon: "home" }
                                    ]

                                    delegate: Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 48
                                        radius: 16
                                        color: settingsSection === modelData.key ? colors.primaryContainer : "transparent"

                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: settingsSection = modelData.key
                                        }

                                        Row {
                                            anchors.verticalCenter: parent.verticalCenter
                                            anchors.left: parent.left
                                            anchors.leftMargin: 12
                                            spacing: 8

                                            Text {
                                                text: glyph(modelData.icon)
                                                color: settingsSection === modelData.key ? colors.onPrimary : colors.text
                                                font.family: backend.materialFontFamily
                                                font.pixelSize: 18
                                            }

                                            Text {
                                                text: modelData.title
                                                color: settingsSection === modelData.key ? colors.onPrimary : colors.text
                                                font.family: backend.uiFontFamily
                                                font.pixelSize: 12
                                                font.weight: Font.Medium
                                            }
                                        }
                                    }
                                }

                                Item { Layout.fillHeight: true }
                            }
                        }

                        ScrollView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            ScrollBar.vertical.policy: ScrollBar.AlwaysOff

                            StackLayout {
                                width: parent.width
                                currentIndex: settingsSection === "overview" ? 0 : settingsSection === "appearance" ? 1 : 2

                                ColumnLayout {
                                    width: parent.width
                                    spacing: 12

                                    Text {
                                        text: "System Overview"
                                        color: colors.text
                                        font.family: "Outfit"
                                        font.pixelSize: 24
                                        font.weight: Font.Medium
                                    }

                                    Text {
                                        text: "Quick telemetry for this session and shell environment."
                                        color: colors.textMuted
                                        font.family: backend.uiFontFamily
                                        font.pixelSize: 12
                                    }

                                    GridLayout {
                                        columns: 2
                                        columnSpacing: 10
                                        rowSpacing: 10

                                        Repeater {
                                            model: backend.systemOverview

                                            delegate: Rectangle {
                                                Layout.fillWidth: true
                                                Layout.preferredHeight: 86
                                                radius: 20
                                                color: colors.cardBg
                                                border.width: 1
                                                border.color: colors.panelBorder

                                                Column {
                                                    anchors.fill: parent
                                                    anchors.margins: 12
                                                    spacing: 4

                                                    Text {
                                                        text: modelData.label
                                                        color: colors.textMuted
                                                        font.family: backend.uiFontFamily
                                                        font.pixelSize: 11
                                                    }

                                                    Text {
                                                        text: modelData.value
                                                        color: colors.text
                                                        font.family: backend.uiFontFamily
                                                        font.pixelSize: 13
                                                        font.weight: Font.DemiBold
                                                        wrapMode: Text.WordWrap
                                                        width: parent.width
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                ColumnLayout {
                                    width: parent.width
                                    spacing: 12

                                    Text {
                                        text: "Appearance"
                                        color: colors.text
                                        font.family: "Outfit"
                                        font.pixelSize: 24
                                        font.weight: Font.Medium
                                    }

                                    Text {
                                        text: "Pick an accent preset for the notification center."
                                        color: colors.textMuted
                                        font.family: backend.uiFontFamily
                                        font.pixelSize: 12
                                    }

                                    Text {
                                        text: backend.appearanceStatus
                                        color: colors.textMuted
                                        font.family: backend.uiFontFamily
                                        font.pixelSize: 12
                                    }

                                    RowLayout {
                                        spacing: 10

                                        Repeater {
                                            model: ["orchid", "mint", "sunset"]

                                            delegate: Button {
                                                text: modelData.charAt(0).toUpperCase() + modelData.slice(1)
                                                onClicked: backend.setAccent(modelData)
                                                highlighted: backend.accentName === modelData
                                            }
                                        }
                                    }
                                }

                                ColumnLayout {
                                    width: parent.width
                                    spacing: 12

                                    Text {
                                        text: "Home Assistant"
                                        color: colors.text
                                        font.family: "Outfit"
                                        font.pixelSize: 24
                                        font.weight: Font.Medium
                                    }

                                    Text {
                                        text: "Connect, fetch entities, and pin up to five controls."
                                        color: colors.textMuted
                                        font.family: backend.uiFontFamily
                                        font.pixelSize: 12
                                    }

                                    TextField {
                                        Layout.fillWidth: true
                                        text: backend.haUrl
                                        placeholderText: "https://homeassistant.local:8123"
                                        onTextChanged: backend.setHomeAssistantUrl(text)
                                    }

                                    TextField {
                                        Layout.fillWidth: true
                                        text: backend.haToken
                                        placeholderText: "Long-lived access token"
                                        echoMode: TextInput.Password
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
                                        font.pixelSize: 12
                                        wrapMode: Text.WordWrap
                                        Layout.fillWidth: true
                                    }

                                    Repeater {
                                        model: backend.haEntities

                                        delegate: Rectangle {
                                            Layout.fillWidth: true
                                            radius: 18
                                            color: colors.cardBg
                                            border.width: 1
                                            border.color: modelData.pinned ? colors.primary : colors.panelBorder

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.margins: 12
                                                spacing: 10

                                                ColumnLayout {
                                                    Layout.fillWidth: true
                                                    spacing: 2

                                                    Text {
                                                        text: modelData.name
                                                        color: colors.text
                                                        font.family: backend.uiFontFamily
                                                        font.pixelSize: 13
                                                        font.weight: Font.DemiBold
                                                        elide: Text.ElideRight
                                                    }

                                                    Text {
                                                        text: modelData.entity_id + " • " + modelData.state
                                                        color: colors.textMuted
                                                        font.family: backend.uiFontFamily
                                                        font.pixelSize: 11
                                                        elide: Text.ElideRight
                                                    }
                                                }

                                                Button {
                                                    text: modelData.pinned ? "Unpin" : "Pin"
                                                    onClicked: backend.togglePinEntity(modelData.entity_id)
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
    }
}
