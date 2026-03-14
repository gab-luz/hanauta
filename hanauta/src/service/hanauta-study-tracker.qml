import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Window {
    id: root
    width: 860
    height: 680
    visible: true
    color: "transparent"
    title: "Study Tracker"
    flags: Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint

    QtObject {
        id: fallbackTracker
        property var palette: ({
            primary: "#D0BCFF",
            onPrimary: "#381E72",
            primaryContainer: "#4F378B",
            onPrimaryContainer: "#EADDFF",
            secondary: "#CCC2DC",
            onSecondary: "#332D41",
            tertiary: "#EFB8C8",
            surfaceContainer: "#211F26",
            surfaceContainerHigh: "#2B2930",
            panelBorder: "#938F9947",
            accentSoft: "#D0BCFF2E",
            text: "#E6E0E9",
            textMuted: "#CAC4D0C7",
            error: "#F2B8B5",
            onError: "#601410"
        })
        property var subjects: []
        property var recentSessions: []
        property var todaySessions: []
        property int todayMinutes: 0
        property int weekMinutes: 0
        property string currentSubject: ""
        property string currentType: "language"
        property bool isTracking: false
        property int elapsedSeconds: 0
        property string materialFontFamily: "Material Symbols Rounded"
        function materialIcon(name) { return name }
        function startTracking() {}
        function stopTracking() {}
        function deleteSession(sessionId) {}
        function addSubject(name, type) {}
        function removeSubject(name) {}
        function quit() {}
    }

    property var tracker: (typeof backend !== "undefined" && backend) ? backend : fallbackTracker
    property var colors: tracker.palette
    property int activePane: 0
    property string draftSubjectType: tracker.currentType || "language"

    function glyph(name) {
        return tracker.materialIcon(name)
    }

    function formatMinutes(minutes) {
        if (minutes < 60) {
            return minutes + "m"
        }
        var hours = Math.floor(minutes / 60)
        var mins = minutes % 60
        return mins === 0 ? hours + "h" : hours + "h " + mins + "m"
    }

    function formatElapsed(seconds) {
        var h = Math.floor(seconds / 3600)
        var m = Math.floor((seconds % 3600) / 60)
        var s = seconds % 60
        if (h > 0) {
            return h + ":" + pad(m) + ":" + pad(s)
        }
        return m + ":" + pad(s)
    }

    function pad(n) {
        return n < 10 ? "0" + n : n
    }

    function selectSubject(name, type) {
        tracker.currentSubject = name
        tracker.currentType = type
        draftSubjectType = type
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"

        Rectangle {
            anchors.fill: parent
            anchors.margins: 16
            radius: 28
            color: colors.surfaceContainer
            border.width: 1
            border.color: colors.panelBorder

            GridLayout {
                anchors.fill: parent
                rowSpacing: 0
                columnSpacing: 0
                columns: 2

                Rectangle {
                    Layout.fillHeight: true
                    Layout.preferredWidth: 186
                    topLeftRadius: 28
                    bottomLeftRadius: 28
                    color: colors.surfaceContainer

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 22
                        anchors.rightMargin: 22
                        anchors.topMargin: 26
                        anchors.bottomMargin: 22
                        spacing: 12

                        Rectangle {
                            Layout.preferredWidth: 120
                            Layout.preferredHeight: 44
                            radius: 16
                            color: colors.primaryContainer

                            Row {
                                anchors.centerIn: parent
                                spacing: 8

                                Text {
                                    text: glyph("study")
                                    color: colors.onPrimaryContainer
                                    font.family: tracker.materialFontFamily
                                    font.pixelSize: 18
                                }

                                Text {
                                    text: "Tracker"
                                    color: colors.onPrimaryContainer
                                    font.family: "Outfit"
                                    font.pixelSize: 16
                                    font.weight: Font.Medium
                                }
                            }
                        }

                        Repeater {
                            model: [
                                { label: "overview", title: "Overview", icon: "dashboard" },
                                { label: "subjects", title: "Subjects", icon: "book" },
                                { label: "sessions", title: "Sessions", icon: "timer" }
                            ]

                            delegate: Item {
                                Layout.fillWidth: true
                                implicitHeight: 62

                                readonly property bool selected: activePane === index

                                Rectangle {
                                    anchors.fill: parent
                                    radius: 22
                                    color: selected ? colors.secondary + "33" : "transparent"
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: activePane = index
                                }

                                Row {
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left
                                    anchors.leftMargin: 18
                                    spacing: 14

                                    Text {
                                        text: glyph(modelData.icon)
                                        color: selected ? colors.onSecondary : colors.text
                                        font.family: tracker.materialFontFamily
                                        font.pixelSize: 20
                                    }

                                    Column {
                                        spacing: 2

                                        Text {
                                            text: modelData.title
                                            color: selected ? colors.onSecondary : colors.text
                                            font.family: "Inter"
                                            font.pixelSize: 14
                                            font.weight: Font.Medium
                                        }

                                        Text {
                                            text: modelData.label
                                            color: selected ? colors.onSecondary + "CC" : colors.textMuted
                                            font.family: "Inter"
                                            font.pixelSize: 11
                                            font.capitalization: Font.AllLowercase
                                        }
                                    }
                                }
                            }
                        }

                        Item { Layout.fillHeight: true }

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 82
                            radius: 22
                            color: colors.primaryContainer

                            Column {
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 4

                                Text {
                                    text: tracker.isTracking ? "Now studying" : "Ready"
                                    color: colors.onPrimaryContainer + "CC"
                                    font.family: "Inter"
                                    font.pixelSize: 12
                                }

                                Text {
                                    text: tracker.isTracking ? formatElapsed(tracker.elapsedSeconds) : "Start a session"
                                    color: colors.onPrimaryContainer
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: 18
                                    font.weight: Font.DemiBold
                                }

                                Text {
                                    text: tracker.isTracking ? tracker.currentSubject : "Choose a subject in Overview"
                                    color: colors.onPrimaryContainer + "CC"
                                    font.family: "Inter"
                                    font.pixelSize: 12
                                    elide: Text.ElideRight
                                    width: parent.width
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    id: paneArea
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    topRightRadius: 28
                    bottomRightRadius: 28
                    color: colors.surfaceContainerHigh

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 28
                        spacing: 18

                        RowLayout {
                            Layout.fillWidth: true

                            ColumnLayout {
                                spacing: 4

                                Text {
                                    text: ["Overview", "Subjects", "Sessions"][activePane]
                                    color: colors.text
                                    font.family: "Outfit"
                                    font.pixelSize: 30
                                    font.weight: Font.Medium
                                }

                                Text {
                                    text: activePane === 0
                                        ? "Inspired by the Caelestia control-center layout"
                                        : activePane === 1
                                            ? "Manage what you study without leaving the shell"
                                            : "Recent history in compact cards"
                                    color: colors.textMuted
                                    font.family: "Inter"
                                    font.pixelSize: 13
                                }
                            }

                            Item { Layout.fillWidth: true }

                            ToolButton {
                                text: glyph("close")
                                onClicked: tracker.quit()
                                background: Rectangle {
                                    radius: width / 2
                                    color: parent.hovered ? colors.accentSoft : "transparent"
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: colors.text
                                    font.family: tracker.materialFontFamily
                                    font.pixelSize: 18
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }

                        StackLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            currentIndex: activePane

                            ScrollView {
                                clip: true
                                ScrollBar.vertical.policy: ScrollBar.AlwaysOff
                                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                                ColumnLayout {
                                    width: parent.width
                                    spacing: 16

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 16

                                        Repeater {
                                            model: [
                                                { title: "Today", value: formatMinutes(tracker.todayMinutes), caption: tracker.todaySessions.length + " sessions", tone: colors.primary },
                                                { title: "This week", value: formatMinutes(tracker.weekMinutes), caption: tracker.recentSessions.length + " recent items", tone: colors.secondary }
                                            ]

                                            delegate: Rectangle {
                                                Layout.fillWidth: true
                                                Layout.preferredHeight: 132
                                                radius: 24
                                                color: colors.surfaceContainer
                                                border.width: 1
                                                border.color: colors.panelBorder

                                                Column {
                                                    anchors.fill: parent
                                                    anchors.margins: 18
                                                    spacing: 8

                                                    Text {
                                                        text: modelData.title
                                                        color: colors.textMuted
                                                        font.family: "Inter"
                                                        font.pixelSize: 12
                                                    }

                                                    Text {
                                                        text: modelData.value
                                                        color: modelData.tone
                                                        font.family: "Outfit"
                                                        font.pixelSize: 32
                                                        font.weight: Font.Medium
                                                    }

                                                    Text {
                                                        text: modelData.caption
                                                        color: colors.text
                                                        font.family: "Inter"
                                                        font.pixelSize: 13
                                                        elide: Text.ElideRight
                                                        width: parent.width
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        radius: 24
                                        color: tracker.isTracking ? colors.primaryContainer : colors.surfaceContainer
                                        border.width: 1
                                        border.color: tracker.isTracking ? colors.primary : colors.panelBorder

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.margins: 20
                                            spacing: 16

                                            Rectangle {
                                                Layout.preferredWidth: 56
                                                Layout.preferredHeight: 56
                                                radius: 18
                                                color: tracker.isTracking ? colors.onPrimaryContainer + "22" : colors.secondary + "22"

                                                Text {
                                                    anchors.centerIn: parent
                                                    text: glyph("timer")
                                                    color: tracker.isTracking ? colors.onPrimaryContainer : colors.secondary
                                                    font.family: tracker.materialFontFamily
                                                    font.pixelSize: 24
                                                }
                                            }

                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 4

                                                Text {
                                                    text: tracker.isTracking ? "Session live" : "Session idle"
                                                    color: tracker.isTracking ? colors.onPrimaryContainer + "CC" : colors.textMuted
                                                    font.family: "Inter"
                                                    font.pixelSize: 12
                                                }

                                                Text {
                                                    text: tracker.isTracking ? formatElapsed(tracker.elapsedSeconds) : "Ready to start"
                                                    color: tracker.isTracking ? colors.onPrimaryContainer : colors.text
                                                    font.family: "JetBrains Mono"
                                                    font.pixelSize: 24
                                                    font.weight: Font.DemiBold
                                                }

                                                Text {
                                                    text: tracker.isTracking ? tracker.currentSubject : "Pick a subject below and start tracking"
                                                    color: tracker.isTracking ? colors.onPrimaryContainer + "CC" : colors.textMuted
                                                    font.family: "Inter"
                                                    font.pixelSize: 12
                                                    elide: Text.ElideRight
                                                    Layout.fillWidth: true
                                                }
                                            }

                                            Button {
                                                onClicked: {
                                                    if (tracker.isTracking) {
                                                        tracker.stopTracking()
                                                    } else {
                                                        tracker.startTracking()
                                                    }
                                                }
                                                background: Rectangle {
                                                    radius: 999
                                                    color: tracker.isTracking ? colors.onPrimaryContainer : colors.primaryContainer
                                                }
                                                contentItem: Text {
                                                    text: tracker.isTracking ? "Stop" : "Start"
                                                    color: tracker.isTracking ? colors.primaryContainer : colors.onPrimaryContainer
                                                    font.family: "Inter"
                                                    font.pixelSize: 13
                                                    font.weight: Font.Medium
                                                    horizontalAlignment: Text.AlignHCenter
                                                    verticalAlignment: Text.AlignVCenter
                                                }
                                            }
                                        }
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        radius: 24
                                        color: colors.surfaceContainer
                                        border.width: 1
                                        border.color: colors.panelBorder

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 20
                                            spacing: 14

                                            RowLayout {
                                                Layout.fillWidth: true

                                                ColumnLayout {
                                                    spacing: 3

                                                    Text {
                                                        text: "Quick start"
                                                        color: colors.text
                                                        font.family: "Outfit"
                                                        font.pixelSize: 20
                                                        font.weight: Font.Medium
                                                    }

                                                    Text {
                                                        text: "Same functionality, but arranged like a Caelestia pane"
                                                        color: colors.textMuted
                                                        font.family: "Inter"
                                                        font.pixelSize: 12
                                                    }
                                                }

                                                Item { Layout.fillWidth: true }

                                                Button {
                                                    onClicked: {
                                                        if (tracker.isTracking) {
                                                            tracker.stopTracking()
                                                        } else {
                                                            tracker.startTracking()
                                                        }
                                                    }
                                                    background: Rectangle {
                                                        radius: 999
                                                        color: tracker.isTracking ? colors.error : colors.primaryContainer
                                                    }
                                                    contentItem: Row {
                                                        anchors.centerIn: parent
                                                        spacing: 8

                                                        Text {
                                                            text: tracker.isTracking ? glyph("stop") : glyph("play")
                                                            color: tracker.isTracking ? colors.onError : colors.onPrimaryContainer
                                                            font.family: tracker.materialFontFamily
                                                            font.pixelSize: 16
                                                        }

                                                        Text {
                                                            text: tracker.isTracking ? "Stop" : "Start"
                                                            color: tracker.isTracking ? colors.onError : colors.onPrimaryContainer
                                                            font.family: "Inter"
                                                            font.pixelSize: 13
                                                            font.weight: Font.Medium
                                                        }
                                                    }
                                                }
                                            }

                                            ComboBox {
                                                Layout.fillWidth: true
                                                model: tracker.subjects
                                                textRole: "name"
                                                currentIndex: {
                                                    for (var i = 0; i < tracker.subjects.length; i++) {
                                                        if (tracker.subjects[i].name === tracker.currentSubject) {
                                                            return i
                                                        }
                                                    }
                                                    return 0
                                                }
                                                onActivated: {
                                                    if (currentIndex >= 0 && currentIndex < tracker.subjects.length) {
                                                        selectSubject(tracker.subjects[currentIndex].name, tracker.subjects[currentIndex].type)
                                                    }
                                                }
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 10

                                                Repeater {
                                                    model: [
                                                        { key: "language", label: "Language", icon: "language" },
                                                        { key: "programming", label: "Programming", icon: "code" }
                                                    ]

                                                    delegate: Button {
                                                        Layout.fillWidth: true
                                                        onClicked: draftSubjectType = modelData.key
                                                        background: Rectangle {
                                                            radius: 20
                                                            color: draftSubjectType === modelData.key ? colors.secondary + "33" : colors.surfaceContainerHigh
                                                            border.width: 1
                                                            border.color: draftSubjectType === modelData.key ? colors.secondary : colors.panelBorder
                                                        }
                                                        contentItem: Row {
                                                            anchors.centerIn: parent
                                                            spacing: 8

                                                            Text {
                                                                text: glyph(modelData.icon)
                                                                color: draftSubjectType === modelData.key ? colors.onSecondary : colors.text
                                                                font.family: tracker.materialFontFamily
                                                                font.pixelSize: 16
                                                            }

                                                            Text {
                                                                text: modelData.label
                                                                color: draftSubjectType === modelData.key ? colors.onSecondary : colors.text
                                                                font.family: "Inter"
                                                                font.pixelSize: 13
                                                                font.weight: Font.Medium
                                                            }
                                                        }
                                                    }
                                                }
                                            }

                                            Rectangle {
                                                Layout.fillWidth: true
                                                visible: tracker.isTracking
                                                implicitHeight: visible ? 52 : 0
                                                radius: 18
                                                color: colors.primaryContainer

                                                Row {
                                                    anchors.verticalCenter: parent.verticalCenter
                                                    anchors.left: parent.left
                                                    anchors.leftMargin: 16
                                                    spacing: 10

                                                    Text {
                                                        text: glyph("timer")
                                                        color: colors.onPrimaryContainer
                                                        font.family: tracker.materialFontFamily
                                                        font.pixelSize: 16
                                                    }

                                                    Text {
                                                        text: formatElapsed(tracker.elapsedSeconds)
                                                        color: colors.onPrimaryContainer
                                                        font.family: "JetBrains Mono"
                                                        font.pixelSize: 14
                                                        font.weight: Font.DemiBold
                                                    }

                                                    Text {
                                                        text: tracker.currentSubject
                                                        color: colors.onPrimaryContainer + "D0"
                                                        font.family: "Inter"
                                                        font.pixelSize: 12
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        radius: 24
                                        color: colors.surfaceContainer
                                        border.width: 1
                                        border.color: colors.panelBorder

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 20
                                            spacing: 12

                                            RowLayout {
                                                Layout.fillWidth: true

                                                Text {
                                                    text: "Subjects"
                                                    color: colors.text
                                                    font.family: "Outfit"
                                                    font.pixelSize: 20
                                                    font.weight: Font.Medium
                                                }

                                                Item { Layout.fillWidth: true }

                                                Button {
                                                    onClicked: activePane = 1
                                                    background: Rectangle {
                                                        radius: 999
                                                        color: colors.surfaceContainerHigh
                                                        border.width: 1
                                                        border.color: colors.panelBorder
                                                    }
                                                    contentItem: Text {
                                                        text: "Open subject pane"
                                                        color: colors.text
                                                        font.family: "Inter"
                                                        font.pixelSize: 12
                                                    }
                                                }
                                            }

                                            Flow {
                                                width: parent.width
                                                spacing: 10

                                                Repeater {
                                                    model: tracker.subjects

                                                    delegate: Rectangle {
                                                        width: Math.min(230, (paneArea.width - 120) / 2)
                                                        height: 86
                                                        radius: 22
                                                        color: colors.surfaceContainerHigh
                                                        border.width: 1
                                                        border.color: tracker.currentSubject === modelData.name ? colors.secondary : colors.panelBorder

                                                        MouseArea {
                                                            anchors.fill: parent
                                                            onClicked: selectSubject(modelData.name, modelData.type)
                                                        }

                                                        Row {
                                                            anchors.fill: parent
                                                            anchors.margins: 14
                                                            spacing: 12

                                                            Rectangle {
                                                                width: 42
                                                                height: 42
                                                                radius: 21
                                                                color: modelData.type === "language" ? colors.primaryContainer : colors.tertiary + "33"

                                                                Text {
                                                                    anchors.centerIn: parent
                                                                    text: glyph(modelData.type === "language" ? "language" : "code")
                                                                    color: modelData.type === "language" ? colors.onPrimaryContainer : colors.tertiary
                                                                    font.family: tracker.materialFontFamily
                                                                    font.pixelSize: 18
                                                                }
                                                            }

                                                            Column {
                                                                anchors.verticalCenter: parent.verticalCenter
                                                                spacing: 3

                                                                Text {
                                                                    text: modelData.name
                                                                    color: colors.text
                                                                    font.family: "Inter"
                                                                    font.pixelSize: 14
                                                                    font.weight: Font.Medium
                                                                }

                                                                Text {
                                                                    text: modelData.session_count + " sessions"
                                                                    color: colors.textMuted
                                                                    font.family: "Inter"
                                                                    font.pixelSize: 11
                                                                }

                                                                Text {
                                                                    text: formatMinutes(modelData.total_minutes)
                                                                    color: colors.primary
                                                                    font.family: "JetBrains Mono"
                                                                    font.pixelSize: 12
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            ScrollView {
                                clip: true
                                ScrollBar.vertical.policy: ScrollBar.AlwaysOff

                                ColumnLayout {
                                    width: parent.width
                                    spacing: 16

                                    Rectangle {
                                        Layout.fillWidth: true
                                        radius: 24
                                        color: colors.surfaceContainer
                                        border.width: 1
                                        border.color: colors.panelBorder

                                        ColumnLayout {
                                            anchors.fill: parent
                                            anchors.margins: 20
                                            spacing: 14

                                            Text {
                                                text: "Add a subject"
                                                color: colors.text
                                                font.family: "Outfit"
                                                font.pixelSize: 20
                                                font.weight: Font.Medium
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 10

                                                TextField {
                                                    id: subjectField
                                                    Layout.fillWidth: true
                                                    placeholderText: "Subject name"
                                                }

                                                Button {
                                                    onClicked: {
                                                        var name = subjectField.text.trim()
                                                        if (!name.length) {
                                                            return
                                                        }
                                                        tracker.addSubject(name, draftSubjectType)
                                                        subjectField.text = ""
                                                    }
                                                    background: Rectangle {
                                                        radius: 999
                                                        color: colors.primaryContainer
                                                    }
                                                    contentItem: Text {
                                                        text: "Add"
                                                        color: colors.onPrimaryContainer
                                                        font.family: "Inter"
                                                        font.pixelSize: 13
                                                        font.weight: Font.Medium
                                                    }
                                                }
                                            }

                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 10

                                                Repeater {
                                                    model: [
                                                        { key: "language", label: "Language" },
                                                        { key: "programming", label: "Programming" }
                                                    ]

                                                    delegate: Button {
                                                        Layout.fillWidth: true
                                                        onClicked: draftSubjectType = modelData.key
                                                        background: Rectangle {
                                                            radius: 20
                                                            color: draftSubjectType === modelData.key ? colors.secondary + "33" : colors.surfaceContainerHigh
                                                            border.width: 1
                                                            border.color: draftSubjectType === modelData.key ? colors.secondary : colors.panelBorder
                                                        }
                                                        contentItem: Text {
                                                            text: modelData.label
                                                            color: draftSubjectType === modelData.key ? colors.onSecondary : colors.text
                                                            font.family: "Inter"
                                                            font.pixelSize: 13
                                                            font.weight: Font.Medium
                                                            horizontalAlignment: Text.AlignHCenter
                                                            verticalAlignment: Text.AlignVCenter
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    Flow {
                                        width: parent.width
                                        spacing: 12

                                        Repeater {
                                            model: tracker.subjects

                                            delegate: Rectangle {
                                                width: Math.min(280, (paneArea.width - 120) / 2)
                                                height: 108
                                                radius: 24
                                                color: colors.surfaceContainer
                                                border.width: 1
                                                border.color: tracker.currentSubject === modelData.name ? colors.secondary : colors.panelBorder

                                                MouseArea {
                                                    anchors.fill: parent
                                                    onClicked: selectSubject(modelData.name, modelData.type)
                                                }

                                                Column {
                                                    anchors.fill: parent
                                                    anchors.margins: 16
                                                    spacing: 8

                                                    Row {
                                                        width: parent.width
                                                        spacing: 8

                                                        Text {
                                                            text: modelData.name
                                                            color: colors.text
                                                            font.family: "Outfit"
                                                            font.pixelSize: 18
                                                            font.weight: Font.Medium
                                                        }

                                                        Item {
                                                            width: parent.width - 120
                                                            height: 1
                                                        }

                                                        ToolButton {
                                                            visible: !tracker.isTracking
                                                            text: glyph("delete")
                                                            onClicked: tracker.removeSubject(modelData.name)
                                                            background: Rectangle {
                                                                radius: width / 2
                                                                color: parent.hovered ? colors.error + "22" : "transparent"
                                                            }
                                                            contentItem: Text {
                                                                text: parent.text
                                                                color: colors.error
                                                                font.family: tracker.materialFontFamily
                                                                font.pixelSize: 16
                                                                horizontalAlignment: Text.AlignHCenter
                                                                verticalAlignment: Text.AlignVCenter
                                                            }
                                                        }
                                                    }

                                                    Text {
                                                        text: modelData.type
                                                        color: colors.textMuted
                                                        font.family: "Inter"
                                                        font.pixelSize: 12
                                                    }

                                                    Text {
                                                        text: modelData.session_count + " sessions • " + formatMinutes(modelData.total_minutes)
                                                        color: colors.primary
                                                        font.family: "JetBrains Mono"
                                                        font.pixelSize: 12
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }

                            ScrollView {
                                clip: true
                                ScrollBar.vertical.policy: ScrollBar.AlwaysOff

                                ColumnLayout {
                                    width: parent.width
                                    spacing: 12

                                    Repeater {
                                        model: tracker.recentSessions.slice(0, 18)

                                        delegate: Rectangle {
                                            Layout.fillWidth: true
                                            implicitHeight: 86
                                            radius: 24
                                            color: colors.surfaceContainer
                                            border.width: 1
                                            border.color: colors.panelBorder

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.margins: 18
                                                spacing: 14

                                                Rectangle {
                                                    Layout.preferredWidth: 52
                                                    Layout.preferredHeight: 52
                                                    radius: 18
                                                    color: modelData.type === "language" ? colors.primaryContainer : colors.tertiary + "33"

                                                    Text {
                                                        anchors.centerIn: parent
                                                        text: glyph(modelData.type === "language" ? "language" : "code")
                                                        color: modelData.type === "language" ? colors.onPrimaryContainer : colors.tertiary
                                                        font.family: tracker.materialFontFamily
                                                        font.pixelSize: 20
                                                    }
                                                }

                                                ColumnLayout {
                                                    Layout.fillWidth: true
                                                    spacing: 4

                                                    Text {
                                                        text: modelData.subject
                                                        color: colors.text
                                                        font.family: "Inter"
                                                        font.pixelSize: 15
                                                        font.weight: Font.Medium
                                                    }

                                                    Text {
                                                        text: modelData.start_time + " • " + modelData.display_date
                                                        color: colors.textMuted
                                                        font.family: "Inter"
                                                        font.pixelSize: 12
                                                    }
                                                }

                                                Text {
                                                    text: modelData.duration
                                                    color: colors.primary
                                                    font.family: "JetBrains Mono"
                                                    font.pixelSize: 13
                                                    font.weight: Font.DemiBold
                                                }

                                                ToolButton {
                                                    visible: !tracker.isTracking
                                                    text: glyph("delete")
                                                    onClicked: tracker.deleteSession(modelData.id)
                                                    background: Rectangle {
                                                        radius: width / 2
                                                        color: parent.hovered ? colors.error + "22" : "transparent"
                                                    }
                                                    contentItem: Text {
                                                        text: parent.text
                                                        color: colors.error
                                                        font.family: tracker.materialFontFamily
                                                        font.pixelSize: 16
                                                        horizontalAlignment: Text.AlignHCenter
                                                        verticalAlignment: Text.AlignVCenter
                                                    }
                                                }
                                            }
                                        }
                                    }

                                    Text {
                                        visible: tracker.recentSessions.length === 0
                                        text: "No sessions yet."
                                        color: colors.textMuted
                                        font.family: "Inter"
                                        font.pixelSize: 13
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
