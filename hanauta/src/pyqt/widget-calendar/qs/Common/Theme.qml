pragma Singleton

import QtQuick

QtObject {
    readonly property color primary: "#c4a1ff"
    readonly property color surfaceText: "#f4ecff"
    readonly property color surfaceVariantText: "#bcaecf"
    readonly property color surfaceContainerHigh: "#221b2c"

    readonly property int spacingXS: 6
    readonly property int spacingS: 10
    readonly property int spacingM: 14
    readonly property int spacingL: 18

    readonly property int cornerRadius: 12

    readonly property int fontSizeSmall: 12
    readonly property int fontSizeMedium: 14
    readonly property int fontSizeLarge: 18
    readonly property int fontSizeXLarge: 24

    function withAlpha(colorValue, alpha) {
        return Qt.rgba(colorValue.r, colorValue.g, colorValue.b, alpha);
    }
}
