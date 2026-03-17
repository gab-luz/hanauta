import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Effects

Window {
    id: root
    visible: true
    visibility: Window.FullScreen
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "transparent"
    title: "Power Menu"
    property bool confirmationMode: false
    property int confirmChoiceIndex: 0
    property int pendingActionIndex: -1
    property string pendingActionKey: ""
    property string pendingActionLabel: ""
    property string pendingActionIcon: ""
    property color pendingActionColor: "#D0BCFF"

    function openConfirmation(actionKey, actionLabel, actionIcon, actionColor, actionIndex) {
        pendingActionKey = actionKey
        pendingActionLabel = actionLabel
        pendingActionIcon = actionIcon
        pendingActionColor = actionColor
        pendingActionIndex = actionIndex
        confirmChoiceIndex = 1
        confirmationMode = true
        confirmFocusTimer.start()
    }

    function cancelConfirmation() {
        confirmationMode = false
        confirmChoiceIndex = 0
        restoreActionFocusTimer.start()
    }

    function acceptConfirmation() {
        if (!pendingActionKey) {
            cancelConfirmation()
            return
        }
        backend.perform(pendingActionKey)
    }

    function navigateButtons(direction) {
        if (root.confirmationMode) {
            root.confirmChoiceIndex = direction < 0 ? 0 : 1
            confirmFocusTimer.start()
            return
        }

        var currentIndex = findFocusedButtonIndex()
        if (currentIndex === -1) {
            focusButton(0)
            return
        }

        var newIndex = currentIndex + direction
        if (newIndex >= 0 && newIndex < actionsModel.count) {
            focusButton(newIndex)
        }
    }

    function findFocusedButtonIndex() {
        for (var i = 0; i < actionsModel.count; i++) {
            var column = actionFlow.children[i]
            if (column && column.children[0] && column.children[0].activeFocus) {
                return i
            }
        }
        return -1
    }

    function focusButton(index) {
        var column = actionFlow.children[index]
        if (column && column.children[0]) {
            column.children[0].forceActiveFocus()
        }
    }

    function activateFocusedButton() {
        if (root.confirmationMode) {
            if (root.confirmChoiceIndex === 0) {
                root.cancelConfirmation()
            } else {
                root.acceptConfirmation()
            }
            return
        }

        var currentIndex = findFocusedButtonIndex()
        if (currentIndex >= 0) {
            var column = actionFlow.children[currentIndex]
            if (column && column.children[0]) {
                column.children[0].clicked()
            }
        }
    }

    Shortcut {
        sequence: "Escape"
        context: Qt.ApplicationShortcut
        onActivated: backend.close()
    }

    Shortcut {
        sequence: "Left"
        context: Qt.ApplicationShortcut
        onActivated: root.navigateButtons(-1)
    }

    Shortcut {
        sequence: "Right"
        context: Qt.ApplicationShortcut
        onActivated: root.navigateButtons(1)
    }

    Shortcut {
        sequence: "Return"
        context: Qt.ApplicationShortcut
        onActivated: root.activateFocusedButton()
    }

    Shortcut {
        sequence: "Enter"
        context: Qt.ApplicationShortcut
        onActivated: root.activateFocusedButton()
    }

    // Global key handler for ESC and navigation
    Item {
        anchors.fill: parent
    }

    // ===== Theme tokens (matching your Tailwind config) =====
    property color primary: "#D0BCFF"
    property color primaryText: "#381E72"
    property color primaryContainer: "#4F378B"
    property color primaryContainerText: "#EADDFF"
    property color backgroundDark: "#141218"
    property color surfaceDark: "#1E1B2E"     // alpha applied where used
    property color outlineDark: Qt.rgba(147/255, 143/255, 153/255, 0.20)

    property color accent: "#D0BCFF"
    property color danger: "#FFB4AB"
    property color warning: "#FFDDAE"
    property color success: "#B6F2BA"
    property color info: "#C4E7FF"

    // Background image (you can replace with a local file path)
    property url backgroundSource: "https://lh3.googleusercontent.com/aida-public/AB6AXuBxqRB6EuD2Ni-2Qn7OqDRlYAH4rxFxBAQn36euAOFkU-kxobHhZv0jefKFB9_kL2BiEhiUOdhHKZgFTMQcJwcP7-JTGiVJvnzxSiman1MlFlM1gcCVzMLRcpv_zthWjzxbD3FRCmr4wdnIRzied0kL9iDsGYDaAxGwXpIalWtS9M7k1xWjTqk_quRWRt8kwe5wZdPWBDyBfplB_AKQTEGZINtojFIWMC7OBGp-gt6UoKEb70cFwSNR2Duh94aobIWEZmpW_3k3brE"

    // Adaptive tile sizing
    property int tileSize: Math.max(96, Math.min(140, Math.round(Math.min(width, height) * 0.13)))
    property int tileRadius: 24



    // Notifications (errors / feedback)
    Rectangle {
        id: snack
        visible: false
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 24
        height: 48
        radius: 8
        color: Qt.rgba(0, 0, 0, 0.8)
        
        property alias text: snackText.text
        
        Text {
            id: snackText
            anchors.centerIn: parent
            color: "white"
            font.pixelSize: 14
        }
        
        function open() {
            visible = true
            closeTimer.start()
        }
        
        Timer {
            id: closeTimer
            interval: 3000
            onTriggered: snack.visible = false
        }
    }
    Connections {
        target: backend
        function onNotify(message) {
            snack.text = message
            snack.open()
        }
    }

    // ===== Background layer =====
    Item {
        id: bgLayer
        anchors.fill: parent

        Image {
            id: bgImage
            anchors.fill: parent
            source: root.backgroundSource
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            cache: true
            visible: false   // we display the blurred version below
        }

        // Blurred background (approx. of your blur-sm + opacity)
        MultiEffect {
            anchors.fill: parent
            source: bgImage
            blurEnabled: true
            blur: 1.0
            blurMax: 64
            opacity: 0.40
        }

        // Dark overlay (#0f0d13/80)
        Rectangle {
            anchors.fill: parent
            color: "#0f0d13"
            opacity: 0.80
        }
    }

    // ===== Center card (glass panel) =====
    Item {
        id: cardWrap
        anchors.centerIn: parent
        width: Math.min(root.width * 0.92, 760)
        height: contentCol.implicitHeight + 72

        // Card background
        Rectangle {
            id: card
            anchors.fill: parent
            radius: 24
            color: Qt.rgba(0x1E/255, 0x1B/255, 0x2E/255, 0.70) // #1E1B2E / 70%
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.10)

            layer.enabled: true
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowOpacity: 0.37
                shadowBlur: 0.70
                shadowVerticalOffset: 10
                shadowHorizontalOffset: 0
            }
        }

        // Close button (top-right)
        ToolButton {
            id: closeBtn
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.topMargin: 16
            anchors.rightMargin: 16
            hoverEnabled: true
            onClicked: backend.close()

            background: Rectangle {
                radius: 999
                color: closeBtn.hovered ? Qt.rgba(1, 1, 1, 0.10) : "transparent"
                border.width: 1
                border.color: Qt.rgba(1, 1, 1, closeBtn.hovered ? 0.20 : 0.10)
            }

            contentItem: Text {
                text: "close"
                color: closeBtn.hovered ? "white" : Qt.rgba(1, 1, 1, 0.60)
                font.family: "Material Symbols Rounded"
                font.pixelSize: 22
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        ColumnLayout {
            id: contentCol
            anchors.fill: parent
            anchors.margins: 36
            spacing: 0

            // Title
            Item { Layout.fillWidth: true; height: 4 } // spacer

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                Label {
                    text: "Power Menu"
                    color: "white"
                    font.pixelSize: 28
                    font.weight: 600
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }

                Label {
                    text: root.confirmationMode ? "Confirm your choice" : "Choose an action"
                    color: root.confirmationMode ? Qt.rgba(1, 1, 1, 0.68) : Qt.rgba(1, 1, 1, 0.50)
                    font.pixelSize: 13
                    font.weight: 500
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                    Behavior on color { ColorAnimation { duration: 180 } }
                }
            }

            Item { Layout.fillWidth: true; height: 28 } // spacer

            // Actions model
            ListModel {
                id: actionsModel
                ListElement { key: "shutdown"; label: "Shutdown"; icon: "power_settings_new"; accent: "#FFB4AB"; hoverRotation: 0 }
                ListElement { key: "restart";  label: "Restart";  icon: "restart_alt";        accent: "#FFDDAE"; hoverRotation: 180 }
                ListElement { key: "sleep";    label: "Sleep";    icon: "bedtime";            accent: "#C4E7FF"; hoverRotation: 0 }
                ListElement { key: "logout";   label: "Logout";   icon: "logout";             accent: "#D0BCFF"; hoverRotation: 0 }
            }

            // Buttons in a Flow (wrap like flex-wrap)
            Item {
                Layout.fillWidth: true
                implicitHeight: Math.max(actionFlow.implicitHeight, confirmPane.implicitHeight)

                Flow {
                    id: actionFlow
                    width: parent.width
                    spacing: 28
                    opacity: root.confirmationMode ? 0.0 : 1.0
                    scale: root.confirmationMode ? 0.92 : 1.0
                    visible: opacity > 0.01

                    Behavior on opacity { NumberAnimation { duration: 220 } }
                    Behavior on scale { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }

                    Repeater {
                        model: actionsModel

                        delegate: Column {
                            spacing: 12

                            Button {
                                id: tileBtn
                                width: root.tileSize
                                height: root.tileSize
                                hoverEnabled: true
                                focusPolicy: Qt.StrongFocus
                                property bool tileHighlighted: hovered || activeFocus

                                onClicked: {
                                    root.openConfirmation(model.key, model.label, model.icon, model.accent, index)
                                }

                                background: Item {
                                    anchors.fill: parent

                                    Rectangle {
                                        id: baseRect
                                        anchors.fill: parent
                                        radius: root.tileRadius
                                        color: tileBtn.tileHighlighted ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(1, 1, 1, 0.05)
                                        border.width: tileBtn.activeFocus ? 2 : 1
                                        border.color: tileBtn.activeFocus
                                                      ? Qt.rgba(1, 1, 1, 0.30)
                                                      : (tileBtn.tileHighlighted ? Qt.rgba(1, 1, 1, 0.15) : Qt.rgba(1, 1, 1, 0.10))
                                        Behavior on color { ColorAnimation { duration: 160 } }
                                    }

                                    Rectangle {
                                        anchors.fill: parent
                                        radius: root.tileRadius
                                        color: model.accent
                                        opacity: tileBtn.tileHighlighted ? 0.16 : 0.0
                                        Behavior on opacity { NumberAnimation { duration: 220 } }
                                    }
                                }

                                contentItem: Text {
                                    id: iconText
                                    text: model.icon
                                    color: model.accent
                                    font.family: "Material Symbols Rounded"
                                    font.pixelSize: Math.round(root.tileSize * 0.42)
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                    anchors.centerIn: parent

                                    transformOrigin: Item.Center
                                    scale: tileBtn.tileHighlighted ? 1.10 : 1.0
                                    rotation: tileBtn.tileHighlighted ? model.hoverRotation : 0

                                    Behavior on scale { NumberAnimation { duration: 220 } }
                                    Behavior on rotation { NumberAnimation { duration: 500 } }
                                }
                            }

                            Label {
                                width: root.tileSize
                                text: model.label
                                horizontalAlignment: Text.AlignHCenter
                                font.pixelSize: 13
                                font.weight: 600
                                color: tileBtn.tileHighlighted ? model.accent : Qt.rgba(209/255, 213/255, 219/255, 1.0)
                                Behavior on color { ColorAnimation { duration: 180 } }
                            }
                        }
                    }
                }

                Item {
                    id: confirmPane
                    anchors.fill: parent
                    visible: opacity > 0.01
                    opacity: root.confirmationMode ? 1.0 : 0.0
                    scale: root.confirmationMode ? 1.0 : 0.96
                    implicitHeight: confirmColumn.implicitHeight

                    Behavior on opacity { NumberAnimation { duration: 220 } }
                    Behavior on scale { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }

                    Column {
                        id: confirmColumn
                        anchors.centerIn: parent
                        width: Math.min(parent.width, 520)
                        spacing: 18

                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: 96
                            height: 96
                            radius: 30
                            color: Qt.rgba(1, 1, 1, 0.08)
                            border.width: 1
                            border.color: Qt.rgba(1, 1, 1, 0.12)

                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: 8
                                radius: 24
                                color: root.pendingActionColor
                                opacity: 0.18
                            }

                            Text {
                                anchors.centerIn: parent
                                text: root.pendingActionIcon
                                color: root.pendingActionColor
                                font.family: "Material Symbols Rounded"
                                font.pixelSize: 42
                            }
                        }

                        Label {
                            width: parent.width
                            text: root.pendingActionLabel ? ("Are you sure you want to " + root.pendingActionLabel + "?") : "Confirm this action?"
                            wrapMode: Text.WordWrap
                            horizontalAlignment: Text.AlignHCenter
                            color: "white"
                            font.pixelSize: 24
                            font.weight: 700
                        }

                        Label {
                            width: parent.width
                            text: "This will happen immediately."
                            wrapMode: Text.WordWrap
                            horizontalAlignment: Text.AlignHCenter
                            color: Qt.rgba(1, 1, 1, 0.58)
                            font.pixelSize: 13
                            font.weight: 500
                        }

                        Row {
                            anchors.horizontalCenter: parent.horizontalCenter
                            spacing: 18

                            Button {
                                id: noButton
                                width: 152
                                height: 58
                                hoverEnabled: true
                                focusPolicy: Qt.StrongFocus
                                onClicked: root.cancelConfirmation()

                                background: Rectangle {
                                    radius: 20
                                    color: (noButton.hovered || noButton.activeFocus || root.confirmChoiceIndex === 0)
                                           ? Qt.rgba(1, 1, 1, 0.12)
                                           : Qt.rgba(1, 1, 1, 0.05)
                                    border.width: (noButton.activeFocus || root.confirmChoiceIndex === 0) ? 2 : 1
                                    border.color: (noButton.activeFocus || root.confirmChoiceIndex === 0)
                                                  ? Qt.rgba(1, 1, 1, 0.30)
                                                  : Qt.rgba(1, 1, 1, 0.12)
                                    Behavior on color { ColorAnimation { duration: 160 } }
                                }

                                contentItem: Item {
                                    implicitWidth: noRow.implicitWidth
                                    implicitHeight: noRow.implicitHeight

                                    Row {
                                        id: noRow
                                        anchors.centerIn: parent
                                        spacing: 8

                                        Text {
                                            text: "close"
                                            color: "white"
                                            font.family: "Material Symbols Rounded"
                                            font.pixelSize: 20
                                            anchors.verticalCenter: parent.verticalCenter
                                        }

                                        Text {
                                            text: "No"
                                            color: "white"
                                            font.pixelSize: 15
                                            font.weight: 700
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                }
                            }

                            Button {
                                id: yesButton
                                width: 152
                                height: 58
                                hoverEnabled: true
                                focusPolicy: Qt.StrongFocus
                                onClicked: root.acceptConfirmation()

                                background: Rectangle {
                                    radius: 20
                                    color: (yesButton.hovered || yesButton.activeFocus || root.confirmChoiceIndex === 1)
                                           ? Qt.rgba(root.pendingActionColor.r, root.pendingActionColor.g, root.pendingActionColor.b, 0.22)
                                           : Qt.rgba(root.pendingActionColor.r, root.pendingActionColor.g, root.pendingActionColor.b, 0.14)
                                    border.width: (yesButton.activeFocus || root.confirmChoiceIndex === 1) ? 2 : 1
                                    border.color: (yesButton.activeFocus || root.confirmChoiceIndex === 1)
                                                  ? Qt.rgba(1, 1, 1, 0.38)
                                                  : Qt.rgba(1, 1, 1, 0.18)
                                    Behavior on color { ColorAnimation { duration: 160 } }
                                }

                                contentItem: Item {
                                    implicitWidth: yesRow.implicitWidth
                                    implicitHeight: yesRow.implicitHeight

                                    Row {
                                        id: yesRow
                                        anchors.centerIn: parent
                                        spacing: 8

                                        Text {
                                            text: "check"
                                            color: root.pendingActionColor
                                            font.family: "Material Symbols Rounded"
                                            font.pixelSize: 20
                                            anchors.verticalCenter: parent.verticalCenter
                                        }

                                        Text {
                                            text: "Yes"
                                            color: "white"
                                            font.pixelSize: 15
                                            font.weight: 700
                                            anchors.verticalCenter: parent.verticalCenter
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Item { Layout.fillWidth: true; height: 28 } // spacer

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: Qt.rgba(1, 1, 1, 0.05)
            }

            Item { Layout.fillWidth: true; height: 18 } // spacer

            Label {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                color: Qt.rgba(1, 1, 1, 0.30)
                font.family: "JetBrains Mono"
                font.pixelSize: 11
                text: backend ? ("Uptime: " + backend.uptime + " • User: " + backend.username) : "Loading..."
            }
        }
    }

    // Set initial focus when window opens
    Component.onCompleted: {
        focusTimer.start()
    }
    
    Timer {
        id: focusTimer
        interval: 100
        onTriggered: {
            // Focus the first power button (shutdown)
            var firstColumn = actionFlow.children[0]
            if (firstColumn && firstColumn.children[0]) {
                firstColumn.children[0].forceActiveFocus()
            }
        }
    }

    Timer {
        id: confirmFocusTimer
        interval: 80
        onTriggered: {
            if (root.confirmChoiceIndex === 0) {
                noButton.forceActiveFocus()
            } else {
                yesButton.forceActiveFocus()
            }
        }
    }

    Timer {
        id: restoreActionFocusTimer
        interval: 80
        onTriggered: {
            if (root.pendingActionIndex >= 0) {
                var targetColumn = actionFlow.children[root.pendingActionIndex]
                if (targetColumn && targetColumn.children[0]) {
                    targetColumn.children[0].forceActiveFocus()
                    return
                }
            }
            focusTimer.start()
        }
    }
}
