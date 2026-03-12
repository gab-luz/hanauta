import QtQuick
import "theme.js" as Theme

Item {
    id: root

    required property string bufferText
    required property int failurePulse
    property bool busy: false

    implicitWidth: 360
    implicitHeight: 44

    function syncTokens() {
        var targetLength = root.bufferText.length
        while (tokenModel.count < targetLength) {
            tokenModel.append({
                colorIndex: tokenModel.count % Theme.shapes.length,
                shapeIndex: tokenModel.count % 4
            })
        }
        while (tokenModel.count > targetLength) {
            tokenModel.remove(tokenModel.count - 1)
        }
    }

    onBufferTextChanged: syncTokens()
    Component.onCompleted: syncTokens()

    ListModel {
        id: tokenModel
    }

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: "#20182d"
        border.width: 1
        border.color: flashAnim.running ? Theme.error : Qt.rgba(1, 1, 1, 0.08)
    }

    Text {
        id: placeholder
        anchors.centerIn: parent
        text: root.busy ? "Loading..." : "Enter your password"
        color: Theme.textDim
        font.pixelSize: 15
        font.family: "JetBrains Mono"
        opacity: root.bufferText.length === 0 ? 1 : 0

        Behavior on opacity {
            NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
        }
    }

    ListView {
        id: tokenList
        anchors.centerIn: parent
        anchors.horizontalCenterOffset: contentWidth > root.width ? -(contentWidth - root.width) / 2 : 0
        width: Math.min(contentWidth, root.width - 28)
        height: 22
        orientation: ListView.Horizontal
        spacing: 8
        interactive: false
        clip: true
        model: tokenModel

        add: Transition {
            ParallelAnimation {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 150 }
                NumberAnimation { property: "scale"; from: 0.1; to: 1.0; duration: 240; easing.type: Easing.OutBack }
                NumberAnimation { property: "rotation"; duration: 240; easing.type: Easing.OutCubic }
            }
        }

        remove: Transition {
            SequentialAnimation {
                PropertyAction { property: "ListView.delayRemove"; value: true }
                ParallelAnimation {
                    NumberAnimation { property: "opacity"; to: 0; duration: 120 }
                    NumberAnimation { property: "scale"; to: 0.5; duration: 140; easing.type: Easing.InCubic }
                }
                PropertyAction { property: "ListView.delayRemove"; value: false }
            }
        }

        displaced: Transition {
            NumberAnimation { properties: "x"; duration: 180; easing.type: Easing.OutCubic }
        }

        delegate: Item {
            required property int index
            required property int colorIndex
            required property int shapeIndex

            width: 18
            height: 18
            scale: 1
            opacity: 1
            rotation: index % 2 === 0 ? -18 : 18

            Component.onCompleted: rotation = 0

            Rectangle {
                anchors.centerIn: parent
                width: 18
                height: 18
                radius: shapeIndex === 1 ? 9 : 4
                rotation: shapeIndex === 3 ? 45 : 0
                color: Theme.shapes[colorIndex]
                visible: shapeIndex !== 2
            }

            Canvas {
                anchors.centerIn: parent
                width: 18
                height: 18
                visible: shapeIndex === 2

                onPaint: {
                    var ctx = getContext("2d")
                    ctx.reset()
                    ctx.fillStyle = Theme.shapes[colorIndex]
                    ctx.beginPath()
                    ctx.moveTo(width / 2, 1)
                    ctx.lineTo(width - 1, height - 2)
                    ctx.lineTo(1, height - 2)
                    ctx.closePath()
                    ctx.fill()
                }
            }
        }
    }

    SequentialAnimation {
        id: flashAnim

        NumberAnimation { target: root; property: "scale"; from: 1; to: 1.02; duration: 90 }
        NumberAnimation { target: root; property: "scale"; from: 1.02; to: 1; duration: 120 }
    }

    Connections {
        target: root

        function onFailurePulseChanged() {
            flashAnim.restart()
        }
    }
}
