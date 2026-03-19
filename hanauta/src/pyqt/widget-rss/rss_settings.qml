import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    color: "transparent"
    implicitHeight: 920

    property int editingIndex: -1

    ScrollView {
        anchors.fill: parent
        clip: true

        ColumnLayout {
            width: parent.width
            spacing: 14

            Rectangle {
                Layout.fillWidth: true
                radius: 22
                color: rssTheme.panel
                border.width: 1
                border.color: rssTheme.cardBorder
                implicitHeight: 120

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 6

                    Text {
                        text: "RSS Widget Settings"
                        color: rssTheme.text
                        font.pixelSize: 22
                        font.bold: true
                    }

                    Text {
                        text: "Adapted from the DMS QML settings flow: feeds, refresh rhythm, layout options, and notification behavior all live here."
                        color: rssTheme.mutedText
                        wrapMode: Text.WordWrap
                        font.pixelSize: 13
                        Layout.fillWidth: true
                    }

                    Text {
                        text: rssSettings.status
                        color: rssTheme.primary
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                radius: 22
                color: rssTheme.card
                border.width: 1
                border.color: rssTheme.cardBorder
                implicitHeight: 220

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 10

                    Text {
                        text: editingIndex >= 0 ? "Edit Feed" : "Add Feed"
                        color: rssTheme.text
                        font.pixelSize: 17
                        font.bold: true
                    }

                    TextField {
                        id: feedNameField
                        Layout.fillWidth: true
                        placeholderText: "Feed name"
                        text: editingIndex >= 0 && rssSettings.feeds.length > editingIndex ? rssSettings.feeds[editingIndex].name : ""
                    }

                    TextField {
                        id: feedUrlField
                        Layout.fillWidth: true
                        placeholderText: "https://example.com/feed.xml"
                        text: editingIndex >= 0 && rssSettings.feeds.length > editingIndex ? rssSettings.feeds[editingIndex].url : ""
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Button {
                            text: editingIndex >= 0 ? "Update Feed" : "Add Feed"
                            onClicked: {
                                rssSettings.upsertFeed(feedNameField.text, feedUrlField.text, editingIndex)
                                editingIndex = -1
                                feedNameField.text = ""
                                feedUrlField.text = ""
                            }
                        }

                        Button {
                            text: "Cancel"
                            visible: editingIndex >= 0
                            onClicked: {
                                editingIndex = -1
                                feedNameField.text = ""
                                feedUrlField.text = ""
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                radius: 22
                color: rssTheme.card
                border.width: 1
                border.color: rssTheme.cardBorder
                implicitHeight: Math.max(180, feedsColumn.implicitHeight + 36)

                ColumnLayout {
                    id: feedsColumn
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 10

                    Text {
                        text: "Configured Feeds"
                        color: rssTheme.text
                        font.pixelSize: 17
                        font.bold: true
                    }

                    Repeater {
                        model: rssSettings.feeds

                        delegate: Rectangle {
                            required property var modelData
                            required property int index
                            Layout.fillWidth: true
                            radius: 16
                            color: rssTheme.panelAlt
                            border.width: 1
                            border.color: rssTheme.cardBorder
                            implicitHeight: 78

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 10

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4

                                    Text {
                                        text: modelData.name
                                        color: rssTheme.text
                                        font.pixelSize: 14
                                        font.bold: true
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }

                                    Text {
                                        text: modelData.url
                                        color: rssTheme.mutedText
                                        font.pixelSize: 12
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }
                                }

                                Button {
                                    text: "Edit"
                                    onClicked: {
                                        editingIndex = index
                                        feedNameField.text = modelData.name
                                        feedUrlField.text = modelData.url
                                    }
                                }

                                Button {
                                    text: "Remove"
                                    onClicked: rssSettings.removeFeed(index)
                                }
                            }
                        }
                    }

                    Text {
                        visible: rssSettings.feeds.length === 0
                        text: "No feeds configured yet."
                        color: rssTheme.mutedText
                        font.pixelSize: 12
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                radius: 22
                color: rssTheme.card
                border.width: 1
                border.color: rssTheme.cardBorder
                implicitHeight: 210

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 10

                    Text {
                        text: "Sources & Credentials"
                        color: rssTheme.text
                        font.pixelSize: 17
                        font.bold: true
                    }

                    TextField {
                        id: opmlField
                        Layout.fillWidth: true
                        placeholderText: "/path/to/feeds.opml or https://service.example/opml"
                        text: rssSettings.opmlSource
                        onEditingFinished: rssSettings.setOpmlSource(text)
                    }

                    TextField {
                        id: usernameField
                        Layout.fillWidth: true
                        placeholderText: "Optional username"
                        text: rssSettings.username
                        onEditingFinished: rssSettings.setCredentials(text, passwordField.text)
                    }

                    TextField {
                        id: passwordField
                        Layout.fillWidth: true
                        placeholderText: "Optional password"
                        echoMode: TextInput.Password
                        text: rssSettings.password
                        onEditingFinished: rssSettings.setCredentials(usernameField.text, text)
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                radius: 22
                color: rssTheme.card
                border.width: 1
                border.color: rssTheme.cardBorder
                implicitHeight: 420

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 12

                    Text {
                        text: "Behavior"
                        color: rssTheme.text
                        font.pixelSize: 17
                        font.bold: true
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Refresh interval"; color: rssTheme.text; Layout.fillWidth: true }
                        SpinBox { from: 5; to: 180; value: rssSettings.checkIntervalMinutes; onValueModified: rssSettings.setCheckInterval(value) }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Maximum items"; color: rssTheme.text; Layout.fillWidth: true }
                        SpinBox { from: 3; to: 50; value: rssSettings.itemLimit; onValueModified: rssSettings.setItemLimit(value) }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Sort mode"; color: rssTheme.text; Layout.fillWidth: true }
                        ComboBox {
                            model: [
                                { text: "Newest First", value: "newest" },
                                { text: "Oldest First", value: "oldest" },
                                { text: "Group by Feed", value: "byfeed" }
                            ]
                            textRole: "text"
                            valueRole: "value"
                            Component.onCompleted: currentIndex = Math.max(0, indexOfValue(rssSettings.sortMode))
                            onActivated: rssSettings.setSortMode(currentValue)
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        visible: rssSettings.sortMode === "byfeed"
                        Text { text: "Items per feed"; color: rssTheme.text; Layout.fillWidth: true }
                        SpinBox { from: 1; to: 20; value: rssSettings.maxPerFeed; onValueModified: rssSettings.setMaxPerFeed(value) }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "View mode"; color: rssTheme.text; Layout.fillWidth: true }
                        ComboBox {
                            model: [
                                { text: "Expanded", value: "expanded" },
                                { text: "Compact", value: "compact" }
                            ]
                            textRole: "text"
                            valueRole: "value"
                            Component.onCompleted: currentIndex = Math.max(0, indexOfValue(rssSettings.viewMode))
                            onActivated: rssSettings.setViewMode(currentValue)
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Notify on new stories"; color: rssTheme.text; Layout.fillWidth: true }
                        Switch { checked: rssSettings.notifyNewItems; onToggled: rssSettings.setNotifyNewItems(checked) }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Play notification sound"; color: rssTheme.text; Layout.fillWidth: true }
                        Switch { checked: rssSettings.playNotificationSound; onToggled: rssSettings.setPlayNotificationSound(checked) }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Show feed names"; color: rssTheme.text; Layout.fillWidth: true }
                        Switch { checked: rssSettings.showFeedName; onToggled: rssSettings.setShowFeedName(checked) }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Show thumbnails"; color: rssTheme.text; Layout.fillWidth: true }
                        Switch { checked: rssSettings.showImages; onToggled: rssSettings.setShowImages(checked) }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Open links in browser"; color: rssTheme.text; Layout.fillWidth: true }
                        Switch { checked: rssSettings.openInBrowser; onToggled: rssSettings.setOpenInBrowser(checked) }
                    }
                }
            }
        }
    }
}
