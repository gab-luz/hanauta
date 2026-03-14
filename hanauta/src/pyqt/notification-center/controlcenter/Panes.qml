import QtQuick
import QtQuick.Layouts
import "."

Item {
    id: root

    required property Session session
    required property var colors
    required property var backend

    readonly property bool initialOpeningComplete: initialOpeningTimer.triggered

    Timer {
        id: initialOpeningTimer
        interval: 360
        running: true
    }

    ColumnLayout {
        id: layout
        width: parent.width
        spacing: 0
        y: -root.session.activeIndex * root.height

        Behavior on y {
            NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
        }

        Repeater {
            model: PaneRegistry.count

            Loader {
                required property int index
                readonly property var pane: PaneRegistry.getByIndex(index)
                width: root.width
                height: root.height
                active: true
                Component.onCompleted: setSource(pane.component, {
                    "session": root.session,
                    "colors": root.colors,
                    "backend": root.backend
                })
            }
        }
    }
}
