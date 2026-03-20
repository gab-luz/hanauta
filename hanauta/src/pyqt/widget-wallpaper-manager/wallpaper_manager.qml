import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

Window {
    id: root
    visible: true
    visibility: Window.FullScreen
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "transparent"
    title: "Hanauta Wallpaper Manager"

    property int tileWidth: 220
    property int tileHeight: 138
    property int gridColumns: Math.max(1, Math.floor(gridView.width / tileWidth))

    function clampIndex(index) {
        if (backend.wallpapers.length <= 0) {
            return -1
        }
        return Math.max(0, Math.min(index, backend.wallpapers.length - 1))
    }

    function navigate(delta) {
        if (backend.providerSelectionRequired || backend.needsFolderSelection || backend.wallpapers.length <= 0) {
            return
        }
        var nextIndex = clampIndex(backend.currentIndex + delta)
        if (nextIndex >= 0) {
            backend.setCurrentIndex(nextIndex)
            gridView.positionViewAtIndex(nextIndex, GridView.Contain)
        }
    }

    Shortcut {
        sequence: "Escape"
        context: Qt.ApplicationShortcut
        onActivated: backend.closeWindow()
    }

    Shortcut {
        sequence: "Meta+Q"
        context: Qt.ApplicationShortcut
        onActivated: backend.closeWindow()
    }

    Shortcut {
        sequence: "Left"
        context: Qt.ApplicationShortcut
        onActivated: navigate(-1)
    }

    Shortcut {
        sequence: "Right"
        context: Qt.ApplicationShortcut
        onActivated: navigate(1)
    }

    Shortcut {
        sequence: "Up"
        context: Qt.ApplicationShortcut
        onActivated: navigate(-root.gridColumns)
    }

    Shortcut {
        sequence: "Down"
        context: Qt.ApplicationShortcut
        onActivated: navigate(root.gridColumns)
    }

    Shortcut {
        sequence: "Return"
        context: Qt.ApplicationShortcut
        onActivated: backend.activateCurrent()
    }

    Shortcut {
        sequence: "Enter"
        context: Qt.ApplicationShortcut
        onActivated: backend.activateCurrent()
    }

    Shortcut {
        sequence: "Space"
        context: Qt.ApplicationShortcut
        onActivated: backend.activateCurrent()
    }

    Connections {
        target: backend
        function onNotify(message) {
            snackText.text = message
            snack.visible = true
            snackTimer.restart()
        }
    }

    Item {
        anchors.fill: parent

        Image {
            id: bgImage
            anchors.fill: parent
            source: backend.selectedWallpaperUrl !== "" ? backend.selectedWallpaperUrl : backend.backgroundSource
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            cache: true
            visible: false
        }

        MultiEffect {
            anchors.fill: parent
            source: bgImage
            blurEnabled: true
            blur: 1.0
            blurMax: 96
            saturation: 0.05
            opacity: 0.34
        }

        Rectangle {
            anchors.fill: parent
            color: themeModel.overlay
            opacity: 0.52
        }
    }

    Rectangle {
        id: shell
        anchors.fill: parent
        anchors.margins: 34
        radius: 32
        color: "transparent"
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.08)

        Rectangle {
            anchors.fill: parent
            radius: 32
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(0.10, 0.10, 0.14, 0.42) }
                GradientStop { position: 1.0; color: Qt.rgba(0.06, 0.06, 0.10, 0.30) }
            }
        }

        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: themeModel.shadow
            shadowOpacity: 0.42
            shadowBlur: 0.85
            shadowVerticalOffset: 18
        }

        ToolButton {
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.topMargin: 18
            anchors.rightMargin: 18
            z: 5
            text: "×"
            onClicked: backend.closeWindow()
            padding: 0
            implicitWidth: 42
            implicitHeight: 42
            contentItem: Text {
                text: parent.text
                color: themeModel.text
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.family: fontsModel.display
                font.pixelSize: 22
                font.weight: Font.DemiBold
            }
            background: Rectangle {
                radius: 21
                color: Qt.rgba(1, 1, 1, 0.05)
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, 0.12)
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 18

            RowLayout {
                Layout.fillWidth: true
                spacing: 16

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: "WALLPAPER STUDIO"
                        color: themeModel.primary
                        font.family: fontsModel.ui
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }

                    Text {
                        text: backend.currentFolder ? backend.currentFolder : "Choose your wallpaper pack"
                        color: themeModel.text
                        font.family: fontsModel.display
                        font.pixelSize: 24
                        font.weight: Font.DemiBold
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }

                    Text {
                        text: backend.matugenAvailable
                            ? "Wallpapers recolor the desktop widgets through Matugen whenever it is available."
                            : "Wallpapers still apply normally. Widget recoloring only happens when Matugen is installed."
                        color: themeModel.textMuted
                        font.family: fontsModel.ui
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }

                RowLayout {
                    spacing: 10

                    Rectangle {
                        radius: 999
                        color: Qt.rgba(1, 1, 1, 0.05)
                        border.width: 1
                        border.color: Qt.rgba(1, 1, 1, 0.08)
                        implicitHeight: 38
                        implicitWidth: badgeText.implicitWidth + 26

                        Text {
                            id: badgeText
                            anchors.centerIn: parent
                            text: backend.activeProvider ? backend.activeProvider.toUpperCase() : "NO PACK"
                            color: themeModel.primary
                            font.family: fontsModel.ui
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                    }

                    ToolButton {
                        text: "Pack"
                        onClicked: backend.openProviderDialog()
                        padding: 0
                        implicitWidth: 82
                        implicitHeight: 38
                        contentItem: Text {
                            text: parent.text
                            color: themeModel.text
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.family: fontsModel.ui
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }
                        background: Rectangle {
                            radius: 19
                            color: Qt.rgba(1, 1, 1, 0.04)
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.10)
                        }
                    }

                    ToolButton {
                        text: "Refresh"
                        onClicked: {
                            if (backend.activeProvider === "konachan") {
                                backend.fetchKonachanCandidates()
                            } else {
                                backend.refreshProviderContent()
                            }
                        }
                        padding: 0
                        implicitWidth: 88
                        implicitHeight: 38
                        enabled: !backend.busy
                        contentItem: Text {
                            text: parent.text
                            color: themeModel.text
                            opacity: parent.parent.enabled ? 1.0 : 0.45
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.family: fontsModel.ui
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }
                        background: Rectangle {
                            radius: 19
                            color: Qt.rgba(1, 1, 1, 0.04)
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.10)
                        }
                    }

                    ToolButton {
                        text: backend.localRandomizerEnabled ? "Stop Shuffle" : "Shuffle 2m"
                        onClicked: backend.toggleLocalRandomizer()
                        padding: 0
                        implicitWidth: 110
                        implicitHeight: 38
                        enabled: !backend.busy && backend.activeProvider !== "konachan" && backend.activeProvider !== ""
                        contentItem: Text {
                            text: parent.text
                            color: themeModel.text
                            opacity: parent.parent.enabled ? 1.0 : 0.45
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.family: fontsModel.ui
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }
                        background: Rectangle {
                            radius: 19
                            color: backend.localRandomizerEnabled ? themeModel.active : Qt.rgba(1, 1, 1, 0.04)
                            border.width: 1
                            border.color: backend.localRandomizerEnabled ? themeModel.activeBorder : Qt.rgba(1, 1, 1, 0.10)
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 18

                Rectangle {
                    id: previewPanel
                    Layout.preferredWidth: Math.max(320, root.width * 0.25)
                    Layout.fillHeight: true
                    radius: 28
                    color: themeModel.cardDark
                    border.width: 1
                    border.color: themeModel.cardBorder

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 18
                        spacing: 14

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 320
                            radius: 24
                            clip: true
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: themeModel.heroStart }
                                GradientStop { position: 1.0; color: themeModel.heroEnd }
                            }

                            Image {
                                anchors.fill: parent
                                source: backend.selectedWallpaperUrl
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                            }

                            Rectangle {
                                anchors.fill: parent
                                color: "#000000"
                                opacity: 0.16
                            }
                        }

                        Text {
                            text: backend.selectedWallpaperName || "Wallpaper preview"
                            color: themeModel.text
                            font.family: fontsModel.display
                            font.pixelSize: 22
                            font.weight: Font.DemiBold
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Text {
                            text: backend.selectedWallpaperPath || "Select a pack to start populating the grid."
                            color: themeModel.textMuted
                            font.family: fontsModel.ui
                            font.pixelSize: 13
                            wrapMode: Text.WrapAnywhere
                            Layout.fillWidth: true
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            radius: 20
                            color: Qt.rgba(1, 1, 1, 0.04)
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.07)
                            implicitHeight: 144

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 8

                                Text {
                                    text: "LIVE MODE"
                                    color: themeModel.primary
                                    font.family: fontsModel.ui
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    text: backend.activeProvider === "konachan"
                                        ? "Konachan mode downloads a new safe wallpaper every 2 minutes and applies it automatically, even after the manager closes."
                                        : "Arrow keys move the magical focus outline across the grid. Enter or click applies the focused wallpaper and pins the selection. Press Enter or click it again to release that pinned selection."
                                    color: themeModel.text
                                    font.family: fontsModel.ui
                                    font.pixelSize: 13
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        Item { Layout.fillHeight: true }

                        ToolButton {
                            Layout.fillWidth: true
                            implicitHeight: 52
                            text: backend.activeProvider === "konachan" ? "Random" : "Randomize wallpapers"
                            enabled: !backend.providerSelectionRequired && !backend.busy
                            onClicked: {
                                if (backend.activeProvider === "konachan") {
                                    backend.fetchKonachanRandom()
                                } else {
                                    backend.applyRandomWallpaper()
                                }
                            }
                            padding: 0
                            contentItem: Text {
                                text: parent.text
                                color: "#101114"
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                font.family: fontsModel.ui
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                            }
                            background: Rectangle {
                                radius: 18
                                color: themeModel.primary
                                opacity: parent.enabled ? 1.0 : 0.45
                            }
                        }

                        ToolButton {
                            Layout.fillWidth: true
                            implicitHeight: 46
                            text: backend.localRandomizerEnabled ? "Disable 2-Min Shuffle" : "Enable 2-Min Shuffle"
                            visible: backend.activeProvider !== "konachan" && backend.activeProvider !== ""
                            enabled: !backend.providerSelectionRequired && !backend.busy && backend.canUseLocalRandomizer
                            onClicked: backend.toggleLocalRandomizer()
                            padding: 0
                            contentItem: Text {
                                text: parent.text
                                color: themeModel.text
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                font.family: fontsModel.ui
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                            }
                            background: Rectangle {
                                radius: 16
                                color: backend.localRandomizerEnabled ? themeModel.active : Qt.rgba(1, 1, 1, 0.03)
                                border.width: 1
                                border.color: backend.localRandomizerEnabled ? themeModel.activeBorder : themeModel.cardBorder
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 28
                    color: themeModel.card
                    border.width: 1
                    border.color: themeModel.cardBorder

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            Text {
                                text: backend.activeProvider === "konachan"
                                    ? "Konachan live provider"
                                    : backend.wallpapers.length > 0
                                    ? backend.wallpapers.length + " wallpaper(s)"
                                    : "No wallpapers loaded yet"
                                color: themeModel.text
                                font.family: fontsModel.display
                                font.pixelSize: 18
                                font.weight: Font.DemiBold
                            }

                            Item { Layout.fillWidth: true }

                            Text {
                                text: backend.activeProvider === "konachan"
                                    ? "Tags decide the next random wallpaper"
                                    : backend.busy ? "Preparing provider..." : "ESC closes"
                                color: themeModel.textMuted
                                font.family: fontsModel.ui
                                font.pixelSize: 12
                            }
                        }

                        Rectangle {
                            visible: backend.activeProvider === "konachan"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: 24
                            color: themeModel.cardDark
                            border.width: 1
                            border.color: themeModel.cardBorder

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 24
                                spacing: 16

                                Text {
                                    text: "KONACHAN RANDOM"
                                    color: themeModel.primary
                                    font.family: fontsModel.ui
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    text: "Use tags to pull ten fresh Konachan suggestions. Click any thumbnail to apply it, or keep pressing Random to rotate the featured preview until one feels right."
                                    color: themeModel.text
                                    font.family: fontsModel.ui
                                    font.pixelSize: 15
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    radius: 18
                                    color: Qt.rgba(1, 1, 1, 0.04)
                                    border.width: 1
                                    border.color: Qt.rgba(1, 1, 1, 0.10)
                                    implicitHeight: 64

                                    TextField {
                                        id: konachanTagsField
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        text: backend.konachanTags
                                        color: themeModel.text
                                        font.family: fontsModel.ui
                                        font.pixelSize: 14
                                        placeholderText: "rating:safe scenery sky city"
                                        placeholderTextColor: themeModel.textMuted
                                        verticalAlignment: TextInput.AlignVCenter
                                        selectByMouse: true
                                        background: Item {}
                                        onEditingFinished: backend.setKonachanTags(text)
                                    }
                                }

                                Text {
                                    text: "Examples: rating:safe scenery, rating:safe city night, rating:safe clouds water"
                                    color: themeModel.textMuted
                                    font.family: fontsModel.ui
                                    font.pixelSize: 13
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    radius: 20
                                    color: Qt.rgba(1, 1, 1, 0.03)
                                    border.width: 1
                                    border.color: Qt.rgba(1, 1, 1, 0.08)

                                    GridView {
                                        id: konachanGrid
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        clip: true
                                        model: backend.konachanCandidates
                                        cellWidth: 168
                                        cellHeight: 114
                                        boundsBehavior: Flickable.StopAtBounds
                                        interactive: true

                                        delegate: Item {
                                            required property var modelData
                                            required property int index
                                            width: konachanGrid.cellWidth - 10
                                            height: konachanGrid.cellHeight - 10

                                            Rectangle {
                                                anchors.fill: parent
                                                radius: 18
                                                color: index === backend.konachanCurrentIndex ? themeModel.active : themeModel.cardDark
                                                border.width: 1
                                                border.color: index === backend.konachanCurrentIndex ? themeModel.activeBorder : themeModel.cardBorder
                                            }

                                            Rectangle {
                                                anchors.fill: parent
                                                anchors.margins: 2
                                                radius: 16
                                                color: "transparent"
                                                border.width: index === backend.konachanCurrentIndex ? 2 : 0
                                                border.color: index === backend.konachanCurrentIndex ? themeModel.primary : "transparent"
                                            }

                                            Rectangle {
                                                anchors.left: parent.left
                                                anchors.right: parent.right
                                                anchors.top: parent.top
                                                anchors.margins: 8
                                                height: 74
                                                radius: 14
                                                clip: true
                                                color: "#18181f"

                                                Image {
                                                    anchors.fill: parent
                                                    source: modelData.previewUrl
                                                    fillMode: Image.PreserveAspectCrop
                                                    asynchronous: true
                                                    cache: true
                                                }

                                                Rectangle {
                                                    anchors.fill: parent
                                                    color: "#000000"
                                                    opacity: 0.12
                                                }
                                            }

                                            Text {
                                                anchors.left: parent.left
                                                anchors.right: parent.right
                                                anchors.bottom: parent.bottom
                                                anchors.margins: 10
                                                text: modelData.name
                                                color: themeModel.text
                                                font.family: fontsModel.ui
                                                font.pixelSize: 11
                                                font.weight: Font.Medium
                                                elide: Text.ElideRight
                                            }

                                            MouseArea {
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                onEntered: backend.previewKonachanCandidate(index)
                                                onClicked: backend.applyKonachanCandidate(index)
                                            }
                                        }

                                        ScrollBar.vertical: ScrollBar {
                                            policy: ScrollBar.AsNeeded
                                        }
                                    }
                                }
                            }
                        }

                        GridView {
                            id: gridView
                            visible: backend.activeProvider !== "konachan"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            cellWidth: root.tileWidth
                            cellHeight: root.tileHeight + 22
                            model: backend.wallpapers
                            currentIndex: backend.currentIndex
                            boundsBehavior: Flickable.StopAtBounds
                            interactive: true
                            cacheBuffer: 1200

                            delegate: Item {
                                required property var modelData
                                required property int index
                                width: gridView.cellWidth - 10
                                height: gridView.cellHeight - 10

                                Rectangle {
                                    anchors.fill: parent
                                    radius: 22
                                    color: index === backend.pinnedIndex ? themeModel.active : themeModel.cardDark
                                    border.width: 1
                                    border.color: index === backend.pinnedIndex ? themeModel.activeBorder : themeModel.cardBorder
                                }

                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: 2
                                    radius: 20
                                    color: "transparent"
                                    border.width: index === backend.currentIndex ? 2 : 0
                                    border.color: index === backend.currentIndex ? themeModel.primary : "transparent"
                                    opacity: index === backend.currentIndex ? 0.95 : 0.0
                                }

                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: 2
                                    radius: 20
                                    color: "transparent"
                                    border.width: index === backend.currentIndex ? 6 : 0
                                    border.color: index === backend.currentIndex ? Qt.rgba(1, 1, 1, 0.08) : "transparent"
                                    opacity: index === backend.currentIndex ? 1.0 : 0.0
                                }

                                Rectangle {
                                    anchors.fill: parent
                                    anchors.margins: -3
                                    radius: 24
                                    color: "transparent"
                                    border.width: index === backend.currentIndex ? 1 : 0
                                    border.color: index === backend.currentIndex ? Qt.rgba(1, 1, 1, 0.28) : "transparent"
                                    opacity: index === backend.currentIndex ? 1.0 : 0.0
                                }

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.margins: 10
                                    height: 108
                                    radius: 18
                                    clip: true
                                    color: "#18181f"

                                    Image {
                                        anchors.fill: parent
                                        source: modelData.thumbUrl
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                        cache: true
                                    }

                                    Rectangle {
                                        anchors.fill: parent
                                        color: "#000000"
                                        opacity: index === backend.currentIndex ? 0.08 : 0.20
                                    }
                                }

                                Text {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.bottom: parent.bottom
                                    anchors.margins: 12
                                    text: modelData.name
                                    color: themeModel.text
                                    font.family: fontsModel.ui
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                    elide: Text.ElideRight
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onEntered: backend.setCurrentIndex(index)
                                    onClicked: {
                                        backend.setCurrentIndex(index)
                                        backend.activateCurrent()
                                    }
                                }
                            }

                            ScrollBar.vertical: ScrollBar {
                                policy: ScrollBar.AsNeeded
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                radius: 20
                color: Qt.rgba(1, 1, 1, 0.04)
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, 0.07)
                implicitHeight: 56

                Text {
                    anchors.fill: parent
                    anchors.margins: 16
                    text: backend.status
                    color: themeModel.text
                    font.family: fontsModel.ui
                    font.pixelSize: 13
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: backend.providerSelectionRequired
        color: Qt.rgba(0, 0, 0, 0.48)
        z: 8

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(root.width * 0.84, 1080)
            height: 560
            radius: 32
            gradient: Gradient {
                GradientStop { position: 0.0; color: themeModel.panelStart }
                GradientStop { position: 1.0; color: themeModel.panelEnd }
            }
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.12)

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 28
                spacing: 20

                Text {
                    text: "Choose your wallpaper pack"
                    color: themeModel.text
                    font.family: fontsModel.display
                    font.pixelSize: 34
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }

                Text {
                    text: "Hanauta can prepare local packs from D3Ext or JaKooLit, keep your own custom folder, or turn on a live Konachan safe feed that rotates every 2 minutes."
                    color: themeModel.textMuted
                    font.family: fontsModel.ui
                    font.pixelSize: 15
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                GridLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    columns: 2
                    rowSpacing: 16
                    columnSpacing: 16

                    Repeater {
                        model: backend.providers

                        delegate: Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.minimumHeight: 212
                            Layout.preferredHeight: 224
                            radius: 28
                            color: modelData.active ? themeModel.active : themeModel.cardDark
                            border.width: 1
                            border.color: modelData.active ? themeModel.activeBorder : themeModel.cardBorder

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 20
                                spacing: 12

                                RowLayout {
                                    Layout.fillWidth: true

                                    Rectangle {
                                        radius: 999
                                        color: Qt.rgba(1, 1, 1, 0.05)
                                        border.width: 1
                                        border.color: Qt.rgba(1, 1, 1, 0.10)
                                        implicitHeight: 32
                                        implicitWidth: modeText.implicitWidth + 24

                                        Text {
                                            id: modeText
                                            anchors.centerIn: parent
                                            text: String(modelData.mode).toUpperCase()
                                            color: themeModel.primary
                                            font.family: fontsModel.ui
                                            font.pixelSize: 11
                                            font.weight: Font.DemiBold
                                        }
                                    }

                                    Item { Layout.fillWidth: true }

                                    Text {
                                        text: modelData.downloaded ? (modelData.count + " ready") : "new pack"
                                        color: themeModel.textMuted
                                        font.family: fontsModel.ui
                                        font.pixelSize: 12
                                    }
                                }

                                Text {
                                    text: modelData.title
                                    color: themeModel.text
                                    font.family: fontsModel.display
                                    font.pixelSize: 23
                                    font.weight: Font.DemiBold
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }

                                Text {
                                    text: modelData.subtitle
                                    color: themeModel.textMuted
                                    font.family: fontsModel.ui
                                    font.pixelSize: 13
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }

                                Item { Layout.fillHeight: true }

                                ToolButton {
                                    Layout.fillWidth: true
                                    implicitHeight: 64
                                    text: modelData.cta
                                    enabled: !backend.busy
                                    onClicked: backend.selectProvider(modelData.key)
                                    padding: 0
                                    contentItem: Text {
                                        text: parent.text
                                        color: "#101114"
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        font.family: fontsModel.ui
                                        font.pixelSize: 14
                                        font.weight: Font.DemiBold
                                        wrapMode: Text.WordWrap
                                        anchors.centerIn: parent
                                        width: parent.width - 24
                                    }
                                    background: Rectangle {
                                        radius: 18
                                        color: themeModel.primary
                                        opacity: parent.enabled ? 1.0 : 0.45
                                    }
                                }
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    Item { Layout.fillWidth: true }

                    ToolButton {
                        text: "Close"
                        visible: !backend.providerSelectionRequired || backend.activeProvider !== ""
                        onClicked: backend.dismissProviderDialog()
                        padding: 0
                        implicitWidth: 120
                        implicitHeight: 46
                        contentItem: Text {
                            text: parent.text
                            color: themeModel.text
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.family: fontsModel.ui
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        background: Rectangle {
                            radius: 18
                            color: Qt.rgba(1, 1, 1, 0.04)
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.10)
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: backend.needsFolderSelection && !backend.providerSelectionRequired
        color: Qt.rgba(0, 0, 0, 0.36)
        z: 7

        Rectangle {
            anchors.centerIn: parent
            width: 520
            height: 280
            radius: 28
            gradient: Gradient {
                GradientStop { position: 0.0; color: themeModel.panelStart }
                GradientStop { position: 1.0; color: themeModel.panelEnd }
            }
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.12)

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 14

                Text {
                    text: "Choose a custom wallpaper folder"
                    color: themeModel.text
                    font.family: fontsModel.display
                    font.pixelSize: 28
                    font.weight: Font.DemiBold
                    Layout.fillWidth: true
                }

                Text {
                    text: "Your custom provider needs one folder with images. After that, the fullscreen grid will browse it just like the built-in packs."
                    color: themeModel.textMuted
                    font.family: fontsModel.ui
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                Item { Layout.fillHeight: true }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    ToolButton {
                        Layout.fillWidth: true
                        implicitHeight: 50
                        text: "Choose Folder"
                        onClicked: backend.chooseFolder()
                        padding: 0
                        contentItem: Text {
                            text: parent.text
                            color: "#101114"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.family: fontsModel.ui
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        background: Rectangle {
                            radius: 18
                            color: themeModel.primary
                        }
                    }

                    ToolButton {
                        Layout.preferredWidth: 120
                        implicitHeight: 50
                        text: "Back"
                        onClicked: backend.openProviderDialog()
                        padding: 0
                        contentItem: Text {
                            text: parent.text
                            color: themeModel.text
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.family: fontsModel.ui
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        background: Rectangle {
                            radius: 18
                            color: Qt.rgba(1, 1, 1, 0.04)
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.10)
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        id: snack
        visible: false
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        radius: 18
        color: Qt.rgba(0, 0, 0, 0.84)
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.12)
        width: Math.min(root.width * 0.66, snackText.implicitWidth + 34)
        height: snackText.implicitHeight + 20
        z: 9

        Text {
            id: snackText
            anchors.centerIn: parent
            width: parent.width - 26
            color: "white"
            font.family: fontsModel.ui
            font.pixelSize: 13
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }
    }

    Timer {
        id: snackTimer
        interval: 3000
        onTriggered: snack.visible = false
    }
}
