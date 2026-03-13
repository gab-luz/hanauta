import QtQuick
import qs.Common

Text {
    property string name: ""
    property int size: 16

    function glyphFor(iconName) {
        switch (iconName) {
        case "arrow_back":
            return "\u2190";
        case "chevron_left":
            return "\u2039";
        case "chevron_right":
            return "\u203a";
        case "keyboard_arrow_up":
            return "\u25b2";
        case "keyboard_arrow_down":
            return "\u25bc";
        case "lock":
            return "\ud83d\udd12";
        case "refresh":
            return "\u21bb";
        default:
            return iconName;
        }
    }

    text: glyphFor(name)
    color: Theme.surfaceText
    font.pixelSize: size
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
    renderType: Text.QtRendering
}
