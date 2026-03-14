import QtQuick
import "."

QtObject {
    readonly property list<string> panes: PaneRegistry.labels

    property string active: "network"
    property int activeIndex: 0
    property bool navExpanded: true

    onActiveChanged: activeIndex = Math.max(0, panes.indexOf(active))
    onActiveIndexChanged: if (panes[activeIndex]) active = panes[activeIndex]
}
