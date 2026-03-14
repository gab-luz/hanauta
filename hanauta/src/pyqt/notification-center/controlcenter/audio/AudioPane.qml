import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    required property var colors
    property var session
    required property var backend
    QtObject {
        id: fallbackBackend
        property string materialFontFamily: "Material Icons"
        property string uiFontFamily: "Inter"
        property string monoFontFamily: "JetBrains Mono"
        property int volume: 0
        property string mediaCover: ""
        property string mediaTitle: "Press Start"
        property string mediaArtist: "No artist"
        property real mediaProgress: 0
        property string mediaElapsed: "0:00"
        property string mediaTotal: "0:00"
        property string mediaStatus: "Stopped"
        function materialIcon(name) { return name }
        function setVolume(value) {}
        function triggerMediaAction(action) {}
    }
    property var paneBackend: backend || fallbackBackend

    ScrollView {
        anchors.fill: parent
        anchors.margins: 18
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            width: parent.availableWidth
            spacing: 12

            Label {
                text: "Audio"
                color: root.colors.text
                font.family: paneBackend.uiFontFamily
                font.pixelSize: 22
                font.weight: Font.DemiBold
            }

            Label {
                text: "Playback and volume controls in a split-pane layout adapted from Caelestia."
                color: root.colors.textMuted
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 72
                radius: 22
                color: root.colors.cardBg
                border.width: 1
                border.color: root.colors.panelBorder

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 12

                    Text {
                        text: paneBackend.materialIcon("volume_up")
                        font.family: paneBackend.materialFontFamily
                        font.pixelSize: 20
                        color: root.colors.primary
                    }

                    Slider {
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        value: paneBackend.volume
                        live: true
                        onValueChanged: if (pressed) paneBackend.setVolume(Math.round(value))
                    }

                    Label {
                        text: paneBackend.volume + "%"
                        color: root.colors.textMuted
                        font.family: paneBackend.uiFontFamily
                        font.pixelSize: 11
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 190
                radius: 24
                color: root.colors.cardBg
                border.width: 1
                border.color: root.colors.mediaBorder

                Rectangle {
                    anchors.fill: parent
                    radius: 24
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: root.colors.mediaStart }
                        GradientStop { position: 1.0; color: root.colors.mediaEnd }
                    }
                    opacity: 0.9
                }

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 14

                        Rectangle {
                            width: 68
                            height: 68
                            radius: 18
                            color: root.colors.cardStrongBg
                            border.width: 1
                            border.color: root.colors.panelBorder
                            clip: true

                            Image {
                                anchors.fill: parent
                                source: paneBackend.mediaCover
                                fillMode: Image.PreserveAspectCrop
                                visible: source !== ""
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true

                            Label {
                                text: paneBackend.mediaTitle
                                color: root.colors.text
                                font.family: paneBackend.uiFontFamily
                                font.pixelSize: 15
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            Label {
                                text: paneBackend.mediaArtist
                                color: root.colors.primary
                                font.family: paneBackend.uiFontFamily
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
                        color: root.colors.panelBorder

                        Rectangle {
                            width: parent.width * paneBackend.mediaProgress
                            height: parent.height
                            radius: 2
                            color: root.colors.primary
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true

                        Label {
                            text: paneBackend.mediaElapsed
                            color: root.colors.inactive
                            font.family: paneBackend.monoFontFamily
                            font.pixelSize: 10
                        }

                        Item { Layout.fillWidth: true }

                        Button {
                            text: paneBackend.materialIcon("skip_previous")
                            font.family: paneBackend.materialFontFamily
                            onClicked: paneBackend.triggerMediaAction("previous")
                        }

                        Button {
                            text: paneBackend.mediaStatus === "Playing" ? paneBackend.materialIcon("pause") : paneBackend.materialIcon("play_arrow")
                            font.family: paneBackend.materialFontFamily
                            onClicked: paneBackend.triggerMediaAction("toggle")
                        }

                        Button {
                            text: paneBackend.materialIcon("skip_next")
                            font.family: paneBackend.materialFontFamily
                            onClicked: paneBackend.triggerMediaAction("next")
                        }

                        Item { Layout.fillWidth: true }

                        Label {
                            text: paneBackend.mediaTotal
                            color: root.colors.inactive
                            font.family: paneBackend.monoFontFamily
                            font.pixelSize: 10
                        }
                    }
                }
            }
        }
    }
}
