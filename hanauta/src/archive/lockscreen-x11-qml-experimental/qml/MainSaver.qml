import QtQuick

Rectangle {
    width: 1920
    height: 1080
    color: "#09070d"

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
            GradientStop { position: 0.0; color: Qt.rgba(0.02, 0.02, 0.04, 0.18) }
            GradientStop { position: 1.0; color: Qt.rgba(0.02, 0.02, 0.04, 0.30) }
        }
    }

    Center {
        anchors.centerIn: parent
        bridge: authBridge
        saverMode: true
    }
}
