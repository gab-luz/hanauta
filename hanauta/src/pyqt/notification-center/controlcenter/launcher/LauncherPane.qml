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
        property string uiFontFamily: "Inter"
        property string materialFontFamily: "Material Icons"
        function materialIcon(name) { return name }
        function openLauncher() {}
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
                text: "Launcher"
                color: root.colors.text
                font.family: paneBackend.uiFontFamily
                font.pixelSize: 22
                font.weight: Font.DemiBold
            }

            Label {
                text: "This pane keeps Caelestia’s launcher placement and density, but uses Hanauta launch actions."
                color: root.colors.textMuted
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 90
                radius: 22
                color: root.colors.cardBg
                border.width: 1
                border.color: root.colors.panelBorder

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12

                    Text {
                        text: "\ue5c3"
                        font.family: paneBackend.materialFontFamily
                        font.pixelSize: 18
                        color: root.colors.primary
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Label {
                            text: "Open Hanauta launcher"
                            color: root.colors.text
                            font.family: paneBackend.uiFontFamily
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }
                        Label {
                            text: "Open the same launcher the bar uses for desktop applications and Hanauta apps."
                            color: root.colors.textMuted
                            font.family: paneBackend.uiFontFamily
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                        }
                    }

                    Button {
                        text: "Open"
                        onClicked: paneBackend.openLauncher()
                    }
                }
            }
        }
    }
}
