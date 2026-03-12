import QtQuick

Rectangle {
    width: 1920
    height: 1080
    color: "#09070d"
    focus: true

    Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            authBridge.submit()
            event.accepted = true
            return
        }
        if (event.key === Qt.Key_Backspace) {
            authBridge.backspace()
            event.accepted = true
            return
        }
        if (event.key === Qt.Key_Escape) {
            authBridge.clearBuffer()
            event.accepted = true
            return
        }
        if (event.text && event.text.length > 0) {
            authBridge.appendText(event.text)
            event.accepted = true
        }
    }

    Image {
        anchors.fill: parent
        source: authBridge.wallpaperSource
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: false
        visible: source !== ""
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: Qt.rgba(0.02, 0.02, 0.04, 0.20) }
            GradientStop { position: 1.0; color: Qt.rgba(0.02, 0.02, 0.04, 0.36) }
        }
    }

    Center {
        anchors.centerIn: parent
        bridge: authBridge
        saverMode: false
    }
}
