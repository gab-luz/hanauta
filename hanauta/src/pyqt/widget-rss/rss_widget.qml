import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

Window {
    id: root
    visible: true
    width: 428
    height: 732
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    title: "Hanauta RSS"
    property bool reloadPulseVisible: false

    Component.onCompleted: {
        var screen = Screen
        x = screen.width - width - 48
        y = 84
    }

    Connections {
        target: backend
        function onLoadingChanged() {
            if (backend.loading) {
                reloadPulseVisible = true
                reloadPulse.restart()
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: 30
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(0.12, 0.12, 0.16, 0.78) }
            GradientStop { position: 1.0; color: Qt.rgba(0.08, 0.08, 0.12, 0.70) }
        }
        border.width: 1
        border.color: backend.cardBorder

        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowOpacity: 0.36
            shadowBlur: 0.8
            shadowVerticalOffset: 14
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 12

        RowLayout {
            Layout.fillWidth: true

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                Text {
                    text: "RSS DIGEST"
                    color: backend.primary
                    font.pixelSize: 12
                    font.bold: true
                }
            }

            RowLayout {
                spacing: 6

                Repeater {
                    model: [
                        { label: "↻", action: "refresh" },
                        { label: "⚙", action: "settings" },
                        { label: "×", action: "close" }
                    ]

                    delegate: Rectangle {
                        required property var modelData
                        width: 34
                        height: 34
                        radius: 17
                        color: Qt.rgba(1, 1, 1, 0.05)
                        border.width: 1
                        border.color: backend.cardBorder

                        Text {
                            anchors.centerIn: parent
                            text: modelData.label
                            color: backend.primary
                            font.pixelSize: modelData.action === "settings" ? 15 : 18
                            font.bold: true
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                if (modelData.action === "refresh") backend.refresh()
                                else if (modelData.action === "settings") backend.openSettings()
                                else backend.closeWindow()
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            radius: 18
            color: Qt.rgba(1, 1, 1, 0.04)
            border.width: 1
            border.color: backend.cardBorder
            implicitHeight: 42

            RowLayout {
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8

                Text {
                    text: "⌕"
                    color: backend.primary
                    font.pixelSize: 15
                    font.bold: true
                }

                TextField {
                    Layout.fillWidth: true
                    placeholderText: "Search a story, source, or topic"
                    text: backend.searchQuery
                    color: backend.textColor
                    placeholderTextColor: backend.mutedText
                    background: Rectangle { color: "transparent" }
                    onTextChanged: backend.setSearchQuery(text)
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            radius: 24
            gradient: Gradient {
                GradientStop { position: 0.0; color: backend.heroStart }
                GradientStop { position: 1.0; color: backend.heroEnd }
            }
            border.width: 1
            border.color: backend.cardBorder
            implicitHeight: 132

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    Rectangle {
                        radius: 999
                        color: backend.chipColor
                        border.width: 1
                        border.color: backend.chipBorder
                        implicitHeight: 28
                        implicitWidth: 60

                        Text {
                            anchors.centerIn: parent
                            text: "FEEDS"
                            color: backend.primary
                            font.pixelSize: 11
                            font.bold: true
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: backend.loading ? "Refreshing..." : (backend.sourcesCount + " source(s)")
                        color: backend.mutedText
                        font.pixelSize: 12
                    }
                }

                Text {
                    text: backend.itemCount > 0 ? backend.entries[0].title : "No stories loaded yet"
                    color: backend.textColor
                    font.pixelSize: 19
                    font.bold: true
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                Text {
                    text: backend.itemCount > 0 ? backend.entries[0].description : "Add feeds in Settings, then refresh the widget."
                    color: backend.mutedText
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    Layout.fillWidth: true
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Repeater {
                model: [
                    { label: "Sources", value: backend.sourcesCount, note: "configured feeds" },
                    { label: "Items", value: backend.itemCount, note: "loaded stories" }
                ]

                delegate: Rectangle {
                    required property var modelData
                    Layout.fillWidth: true
                    radius: 20
                    color: backend.cardColor
                    border.width: 1
                    border.color: backend.cardBorder
                    implicitHeight: 82

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 4

                        Text {
                            text: String(modelData.label).toUpperCase()
                            color: backend.primary
                            font.pixelSize: 11
                            font.bold: true
                        }

                        Text {
                            text: String(modelData.value)
                            color: backend.textColor
                            font.pixelSize: 18
                            font.bold: true
                        }

                        Text {
                            text: modelData.note
                            color: backend.mutedText
                            font.pixelSize: 11
                        }
                    }
                }
            }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ListView {
                id: feedList
                spacing: 10
                model: backend.filteredEntries

                delegate: Rectangle {
                    required property var modelData
                    width: feedList.width
                    radius: 22
                    color: backend.cardColor
                    border.width: 1
                    border.color: backend.cardBorder
                    implicitHeight: imageThumb.visible ? 134 : 104

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 12

                        Rectangle {
                            id: imageThumb
                            visible: modelData.imageUrl !== ""
                            Layout.preferredWidth: visible ? 112 : 0
                            Layout.preferredHeight: visible ? 84 : 0
                            radius: 16
                            color: backend.backgroundShade
                            clip: true

                            Image {
                                anchors.fill: parent
                                source: modelData.imageUrl
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Rectangle {
                                    radius: 999
                                    color: backend.chipColor
                                    border.width: 1
                                    border.color: backend.chipBorder
                                    implicitHeight: 26
                                    implicitWidth: sourceText.implicitWidth + 18

                                    Text {
                                        id: sourceText
                                        anchors.centerIn: parent
                                        text: modelData.source
                                        color: backend.primary
                                        font.pixelSize: 11
                                        font.bold: true
                                    }
                                }

                                Item { Layout.fillWidth: true }

                                Text {
                                    text: modelData.relativeTime
                                    color: backend.mutedText
                                    font.pixelSize: 11
                                }
                            }

                            Text {
                                text: modelData.title
                                color: backend.textColor
                                font.pixelSize: 14
                                font.bold: true
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }

                            Text {
                                text: modelData.description
                                color: backend.mutedText
                                font.pixelSize: 12
                                wrapMode: Text.WordWrap
                                maximumLineCount: imageThumb.visible ? 3 : 2
                                Layout.fillWidth: true
                            }
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: backend.openLink(modelData.link)
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            radius: 18
            color: Qt.rgba(1, 1, 1, 0.04)
            border.width: 1
            border.color: backend.cardBorder
            implicitHeight: 56

            Text {
                anchors.fill: parent
                anchors.margins: 14
                text: backend.status
                color: backend.textColor
                font.pixelSize: 12
                verticalAlignment: Text.AlignVCenter
                wrapMode: Text.WordWrap
            }
        }
    }

    Item {
        anchors.centerIn: parent
        width: 140
        height: 140
        visible: reloadPulseVisible
        z: 20

        Rectangle {
            id: pulseCore
            anchors.centerIn: parent
            width: 58
            height: 58
            radius: 29
            color: Qt.rgba(1, 1, 1, 0.08)
            border.width: 1
            border.color: backend.primary
        }

        Rectangle {
            id: pulseRingA
            anchors.centerIn: parent
            width: 58
            height: 58
            radius: 29
            color: "transparent"
            border.width: 2
            border.color: backend.primary
            opacity: 0.0
        }

        Rectangle {
            id: pulseRingB
            anchors.centerIn: parent
            width: 58
            height: 58
            radius: 29
            color: "transparent"
            border.width: 2
            border.color: Qt.rgba(1, 1, 1, 0.85)
            opacity: 0.0
        }

        Text {
            anchors.centerIn: parent
            text: "↻"
            color: backend.primary
            font.pixelSize: 28
            font.bold: true
        }
    }

    ParallelAnimation {
        id: reloadPulse
        running: false

        SequentialAnimation {
            loops: 2
            ParallelAnimation {
                NumberAnimation { target: pulseRingA; property: "scale"; from: 1.0; to: 2.2; duration: 650; easing.type: Easing.OutCubic }
                NumberAnimation { target: pulseRingA; property: "opacity"; from: 0.78; to: 0.0; duration: 650; easing.type: Easing.OutCubic }
            }
        }

        SequentialAnimation {
            loops: 2
            PauseAnimation { duration: 140 }
            ParallelAnimation {
                NumberAnimation { target: pulseRingB; property: "scale"; from: 1.0; to: 1.9; duration: 650; easing.type: Easing.OutCubic }
                NumberAnimation { target: pulseRingB; property: "opacity"; from: 0.62; to: 0.0; duration: 650; easing.type: Easing.OutCubic }
            }
        }

        SequentialAnimation {
            loops: 4
            NumberAnimation { target: pulseCore; property: "scale"; from: 1.0; to: 1.08; duration: 180; easing.type: Easing.OutCubic }
            NumberAnimation { target: pulseCore; property: "scale"; from: 1.08; to: 1.0; duration: 180; easing.type: Easing.InOutCubic }
        }

        onStopped: {
            pulseRingA.scale = 1.0
            pulseRingA.opacity = 0.0
            pulseRingB.scale = 1.0
            pulseRingB.opacity = 0.0
            pulseCore.scale = 1.0
            reloadPulseVisible = false
        }
    }
}
