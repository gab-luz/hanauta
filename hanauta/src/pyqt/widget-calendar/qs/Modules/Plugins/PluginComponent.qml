import QtQuick

QtObject {
    id: root

    property string pluginId: ""
    property Component horizontalBarPill
    property Component verticalBarPill
    property Component popoutContent

    property QtObject pluginService: QtObject {
        property var _store: ({})

        function loadPluginData(pluginId, key, defaultValue) {
            var scoped = _store[pluginId];
            if (!scoped || !(key in scoped))
                return defaultValue;
            return scoped[key];
        }

        function savePluginData(pluginId, key, value) {
            var scoped = _store[pluginId];
            if (!scoped) {
                scoped = {};
                _store[pluginId] = scoped;
            }
            scoped[key] = value;
        }
    }
}
