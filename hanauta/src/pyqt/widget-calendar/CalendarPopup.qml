import QtQuick
import QtQuick.Window

Window {
    id: root

    width: 436
    height: 640
    visible: true
    color: "transparent"
    title: "Calendar Popup"
    flags: Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint

    CalendarWidget {
        id: calendarPlugin
        pluginId: "qcalCalendar"
    }

    Rectangle {
        anchors.fill: parent
        radius: 24
        color: "#18141f"
        border.width: 1
        border.color: "#352d40"

        Loader {
            anchors.fill: parent
            anchors.margins: 16
            sourceComponent: calendarPlugin.popoutContent
        }
    }

    Component.onCompleted: {
        var screen = Screen
        if (screen) {
            x = screen.virtualX + Math.round((screen.width - width) / 2)
            y = screen.virtualY + 52
        }
        requestActivate()
    }

    onActiveChanged: {
        if (!active)
            close()
    }
}
