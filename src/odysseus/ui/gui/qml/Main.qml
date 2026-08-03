import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

ApplicationWindow {
    id: root
    width: 1400
    height: 900
    minimumWidth: 1040
    minimumHeight: 700
    visible: true
    title: "Odysseus · Music Discovery"
    color: "#080d18"

    property color panelColor: "#101827"
    property color panelRaised: "#162137"
    property color panelHover: "#1c2a45"
    property color borderColor: "#263957"
    property color primaryText: "#f4f7ff"
    property color secondaryText: "#96a6c3"
    property color accent: "#7898ff"
    property color accentSoft: "#253867"
    property color cyan: "#69ddff"
    property color success: "#71e0ad"
    property color warning: "#ffc66d"
    property color danger: "#ff8797"
    property string uiMode: "recording"
    property bool searchPanelExpanded: true
    readonly property bool hasSearchResults:
        uiMode === "recording"
        ? odysseus.recordingResults.length > 0
        : odysseus.catalogTotalCount > 0

    function openMode(mode) {
        uiMode = mode
        searchPanelExpanded = true
        queueDrawer.close()
    }

    palette.window: root.color
    palette.windowText: root.primaryText
    palette.base: root.panelRaised
    palette.alternateBase: root.panelColor
    palette.text: root.primaryText
    palette.button: root.panelRaised
    palette.buttonText: root.primaryText
    palette.highlight: root.accent
    palette.highlightedText: "#ffffff"
    palette.placeholderText: root.secondaryText

    Rectangle {
        anchors.fill: parent
        z: -10
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#0d1630" }
            GradientStop { position: 0.42; color: root.color }
            GradientStop { position: 1.0; color: "#070b14" }
        }
    }

    Shortcut { sequence: "Ctrl+1"; onActivated: root.openMode("recording") }
    Shortcut { sequence: "Ctrl+2"; onActivated: root.openMode("release") }
    Shortcut { sequence: "Ctrl+3"; onActivated: root.openMode("discography") }
    Shortcut {
        sequence: "Ctrl+Shift+Q"
        onActivated: queueDrawer.open()
    }
    Shortcut {
        sequence: "Ctrl+,"
        onActivated: settingsDrawer.open()
    }

    Drawer {
        id: queueDrawer
        objectName: "queueDrawer"
        edge: Qt.RightEdge
        width: Math.min(450, root.width * 0.46)
        height: root.height
        modal: false
        background: Rectangle {
            color: "#0c1424"
            border.color: root.borderColor
        }
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14
            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "Download queue"
                    color: root.primaryText
                    font.pixelSize: 21
                    font.bold: true
                }
                Item { Layout.fillWidth: true }
                Button {
                    text: "Clear finished"
                    flat: true
                    onClicked: odysseus.clearFinishedQueueItems()
                }
                Button {
                    text: "×"
                    flat: true
                    onClicked: queueDrawer.close()
                }
            }
            Text {
                Layout.fillWidth: true
                text: "Downloads run in the background, one at a time, while you keep browsing."
                color: root.secondaryText
                wrapMode: Text.WordWrap
            }
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 1
                color: root.borderColor
            }
            ListView {
                id: queueList
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 10
                clip: true
                model: odysseus.queueRows
                ScrollBar.vertical: ScrollBar { }
                delegate: Rectangle {
                    width: queueList.width
                    height: 112
                    radius: 12
                    color: root.panelRaised
                    border.color: modelData.status === "Failed"
                                  ? root.danger : root.borderColor
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 7
                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                Layout.fillWidth: true
                                text: modelData.label
                                color: root.primaryText
                                font.bold: true
                                elide: Text.ElideRight
                            }
                            Rectangle {
                                implicitWidth: queueStageText.implicitWidth + 14
                                implicitHeight: 24
                                radius: 8
                                color: modelData.status === "Failed" ? "#4b2634"
                                      : modelData.status === "Completed" ? "#173b34"
                                      : root.accentSoft
                                Text {
                                    id: queueStageText
                                    anchors.centerIn: parent
                                    text: modelData.status === "Downloading"
                                          ? modelData.stage : modelData.status
                                    color: modelData.status === "Failed" ? root.danger
                                          : modelData.status === "Completed" ? root.success
                                          : root.cyan
                                    font.pixelSize: 10
                                    font.bold: true
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            ProgressBar {
                                Layout.fillWidth: true
                                from: 0
                                to: 100
                                value: modelData.progress
                                indeterminate: modelData.status === "Downloading"
                                               && modelData.progress === 0
                            }
                            Text {
                                visible: modelData.status === "Downloading"
                                         && modelData.progress > 0
                                text: Math.round(modelData.progress) + "%"
                                color: root.primaryText
                                font.pixelSize: 10
                                Layout.preferredWidth: 32
                                horizontalAlignment: Text.AlignRight
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: modelData.detail
                            color: root.secondaryText
                            font.pixelSize: 11
                            elide: Text.ElideMiddle
                        }
                    }
                }
                Text {
                    anchors.centerIn: parent
                    visible: queueList.count === 0
                    text: "No downloads queued"
                    color: root.secondaryText
                }
            }
        }
    }

    Drawer {
        id: settingsDrawer
        objectName: "settingsDrawer"
        edge: Qt.RightEdge
        width: Math.min(560, root.width * 0.62)
        height: root.height
        modal: true

        function collectSettings() {
            var values = {}
            for (var index = 0; index < providerRepeater.count; ++index)
                providerRepeater.itemAt(index).collect(values)
            return values
        }

        function clearSecretFields() {
            for (var index = 0; index < providerRepeater.count; ++index)
                providerRepeater.itemAt(index).clearSecrets()
        }

        background: Rectangle {
            color: "#0c1424"
            border.color: root.borderColor
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 22
            spacing: 14

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: "Provider settings"
                    color: root.primaryText
                    font.pixelSize: 21
                    font.bold: true
                }
                Item { Layout.fillWidth: true }
                Button {
                    text: "×"
                    flat: true
                    onClicked: settingsDrawer.close()
                }
            }

            Text {
                Layout.fillWidth: true
                text: "Add optional API credentials without restarting Odysseus. "
                      + "Saved secrets are never displayed again."
                color: root.secondaryText
                wrapMode: Text.WordWrap
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: storageRow.implicitHeight + 20
                radius: 10
                color: odysseus.apiSettings.persistentStorage ? "#12332f" : "#332b20"
                border.color: odysseus.apiSettings.persistentStorage
                              ? "#28584d" : "#665339"
                RowLayout {
                    id: storageRow
                    anchors.fill: parent
                    anchors.margins: 10
                    Text {
                        text: odysseus.apiSettings.persistentStorage ? "🔒" : "⚠"
                        font.pixelSize: 14
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        Text {
                            text: odysseus.apiSettings.storageLabel
                            color: odysseus.apiSettings.persistentStorage
                                   ? root.success : root.warning
                            font.bold: true
                            font.pixelSize: 11
                        }
                        Text {
                            Layout.fillWidth: true
                            text: odysseus.apiSettings.persistentStorage
                                  ? "Credentials are stored by the operating system."
                                  : "Install the keyring dependency to keep credentials after exit."
                            color: root.secondaryText
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                        }
                    }
                    CheckBox {
                        id: showApiSecrets
                        text: "Show while typing"
                    }
                }
            }

            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: availableWidth

                Column {
                    width: parent.width
                    spacing: 10

                    Repeater {
                        id: providerRepeater
                        model: [
                            {
                                key: "youtube",
                                name: "YouTube Data API",
                                description: "Uses the supported search API before the HTML fallback.",
                                configured: odysseus.apiSettings.youtubeConfigured,
                                accent: root.danger,
                                fields: [
                                    { key: "youtube_api_key", label: "API key", secret: true, value: "" }
                                ]
                            },
                            {
                                key: "discogs",
                                name: "Discogs",
                                description: "Raises rate limits and improves catalog reliability.",
                                configured: odysseus.apiSettings.discogsConfigured,
                                accent: root.warning,
                                fields: [
                                    { key: "discogs_user_token", label: "Personal access token", secret: true, value: "" }
                                ]
                            },
                            {
                                key: "spotify",
                                name: "Spotify",
                                description: "Enables digital-edition search and Spotify imports.",
                                configured: odysseus.apiSettings.spotifyConfigured,
                                accent: root.success,
                                fields: [
                                    { key: "spotify_client_id", label: "Client ID", secret: false, value: "" },
                                    { key: "spotify_client_secret", label: "Client secret", secret: true, value: "" }
                                ]
                            },
                            {
                                key: "applemusic",
                                name: "Apple Music",
                                description: "Adds storefront editions, artwork, UPCs, and ISRCs.",
                                configured: odysseus.apiSettings.appleMusicConfigured,
                                accent: "#fa5b78",
                                fields: [
                                    { key: "apple_music_developer_token", label: "Developer token", secret: true, value: "" },
                                    { key: "apple_music_storefront", label: "Storefront country code", secret: false, value: odysseus.apiSettings.storefront }
                                ]
                            },
                            {
                                key: "acoustid",
                                name: "AcoustID",
                                description: "Verifies downloaded audio using Chromaprint fingerprints.",
                                configured: odysseus.apiSettings.acoustidConfigured,
                                accent: root.cyan,
                                fields: [
                                    { key: "acoustid_api_key", label: "Application API key", secret: true, value: "" }
                                ]
                            }
                        ]

                        delegate: Rectangle {
                            required property var modelData
                            property color providerAccent: modelData.accent
                            width: providerRepeater.parent.width
                            height: providerColumn.implicitHeight + 24
                            radius: 12
                            color: root.panelRaised
                            border.color: modelData.configured
                                          ? Qt.rgba(providerAccent.r,
                                                    providerAccent.g,
                                                    providerAccent.b, 0.65)
                                          : root.borderColor

                            function collect(values) {
                                for (var index = 0; index < fieldRepeater.count; ++index) {
                                    var field = fieldRepeater.itemAt(index)
                                    values[field.modelData.key] = field.fieldText
                                }
                            }

                            function clearSecrets() {
                                for (var index = 0; index < fieldRepeater.count; ++index) {
                                    var field = fieldRepeater.itemAt(index)
                                    if (field.modelData.secret)
                                        field.fieldText = ""
                                }
                            }

                            ColumnLayout {
                                id: providerColumn
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 12
                                spacing: 7

                                RowLayout {
                                    Layout.fillWidth: true
                                    Text {
                                        text: modelData.name
                                        color: root.primaryText
                                        font.bold: true
                                        font.pixelSize: 14
                                    }
                                    Rectangle {
                                        implicitWidth: providerState.implicitWidth + 14
                                        implicitHeight: 22
                                        radius: 7
                                        color: modelData.configured ? "#173b34" : "#202b3f"
                                        Text {
                                            id: providerState
                                            anchors.centerIn: parent
                                            text: modelData.configured ? "CONFIGURED" : "OPTIONAL"
                                            color: modelData.configured ? root.success : root.secondaryText
                                            font.pixelSize: 9
                                            font.bold: true
                                        }
                                    }
                                    Item { Layout.fillWidth: true }
                                    Button {
                                        text: "Clear saved"
                                        flat: true
                                        visible: modelData.configured
                                        onClicked: odysseus.clearApiCredentials(modelData.key)
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: modelData.description
                                    color: root.secondaryText
                                    font.pixelSize: 10
                                    wrapMode: Text.WordWrap
                                }

                                Repeater {
                                    id: fieldRepeater
                                    model: modelData.fields
                                    delegate: ColumnLayout {
                                        required property var modelData
                                        property alias fieldText: providerField.text
                                        Layout.fillWidth: true
                                        spacing: 3
                                        Text {
                                            text: modelData.label
                                            color: root.secondaryText
                                            font.pixelSize: 10
                                        }
                                        TextField {
                                            id: providerField
                                            Layout.fillWidth: true
                                            text: modelData.value
                                            placeholderText: providerColumn.parent.modelData.configured
                                                             && modelData.secret
                                                             ? "Configured — leave blank to keep"
                                                             : "Enter " + modelData.label.toLowerCase()
                                            echoMode: modelData.secret && !showApiSecrets.checked
                                                      ? TextInput.Password : TextInput.Normal
                                            selectByMouse: true
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                visible: odysseus.settingsMessage.length > 0
                text: odysseus.settingsMessage
                color: odysseus.settingsMessage.indexOf("saved") >= 0
                       ? root.success : root.secondaryText
                font.pixelSize: 11
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Button {
                    text: "Cancel"
                    flat: true
                    onClicked: settingsDrawer.close()
                }
                Button {
                    text: "Save and apply"
                    highlighted: true
                    onClicked: {
                        if (odysseus.saveApiSettings(settingsDrawer.collectSettings()))
                            settingsDrawer.clearSecretFields()
                    }
                }
            }
        }
    }

    header: ToolBar {
        height: 78
        background: Rectangle {
            color: "#0b1322"
            border.color: root.borderColor
            border.width: 1
        }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 26
            anchors.rightMargin: 26
            spacing: 12

            Rectangle {
                width: 42
                height: 42
                radius: 13
                gradient: Gradient {
                    GradientStop { position: 0; color: root.cyan }
                    GradientStop { position: 1; color: root.accent }
                }
                Text {
                    anchors.centerIn: parent
                    text: "O"
                    color: "white"
                    font.pixelSize: 22
                    font.bold: true
                }
            }
            ColumnLayout {
                spacing: 0
                Text {
                    text: "Odysseus"
                    color: root.primaryText
                    font.pixelSize: 21
                    font.bold: true
                }
                Text {
                    text: root.uiMode === "recording" ? "Recording workspace"
                          : root.uiMode === "release" ? "Full album workspace"
                          : "Discography workspace"
                    color: root.secondaryText
                    font.pixelSize: 12
                }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                implicitWidth: modeRow.implicitWidth + 8
                implicitHeight: 44
                radius: 13
                color: "#0f1a2d"
                border.color: root.borderColor
                RowLayout {
                    id: modeRow
                    anchors.centerIn: parent
                    spacing: 2
                    Repeater {
                        model: [
                            { label: "Recording", mode: "recording", shortcut: "Ctrl+1" },
                            { label: "Full album", mode: "release", shortcut: "Ctrl+2" },
                            { label: "Discography", mode: "discography", shortcut: "Ctrl+3" }
                        ]
                        delegate: Button {
                            required property var modelData
                            text: modelData.label
                            flat: true
                            implicitHeight: 36
                            leftPadding: 14
                            rightPadding: 14
                            ToolTip.visible: hovered
                            ToolTip.text: modelData.label + " workspace · "
                                          + modelData.shortcut
                            background: Rectangle {
                                radius: 9
                                color: root.uiMode === modelData.mode
                                       ? root.accentSoft
                                       : parent.hovered ? root.panelHover : "transparent"
                                border.color: root.uiMode === modelData.mode
                                              ? root.accent : "transparent"
                            }
                            contentItem: Text {
                                text: parent.text
                                color: root.uiMode === modelData.mode
                                       ? root.primaryText : root.secondaryText
                                font.bold: root.uiMode === modelData.mode
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            onClicked: root.openMode(modelData.mode)
                        }
                    }
                }
            }
            BusyIndicator {
                running: odysseus.busy
                visible: running
                implicitWidth: 34
                implicitHeight: 34
            }
            Button {
                text: "Queue (" + odysseus.queueCount + ")"
                highlighted: odysseus.queueCount > 0
                onClicked: queueDrawer.open()
                ToolTip.visible: hovered
                ToolTip.text: "Open background download queue · Ctrl+Shift+Q"
            }
            Button {
                text: root.width >= 1120 ? "Settings" : "⚙"
                onClicked: settingsDrawer.open()
                ToolTip.visible: hovered
                ToolTip.text: "Provider API settings · Ctrl+,"
            }
            Button {
                text: "Downloads folder"
                visible: root.width >= 1080
                onClicked: odysseus.openDownloadsFolder()
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        anchors.topMargin: 20
        anchors.bottomMargin: 20
        spacing: 14

        Rectangle {
            objectName: "recordingSearchPanel"
            visible: root.uiMode === "recording"
            Layout.fillWidth: true
            implicitHeight: root.searchPanelExpanded ? 126 : 58
            radius: 16
            color: root.panelColor
            border.color: root.borderColor
            Behavior on implicitHeight { NumberAnimation { duration: 160 } }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: "Find a recording"
                        color: root.primaryText
                        font.pixelSize: 16
                        font.bold: true
                    }
                    Text {
                        visible: root.searchPanelExpanded
                        text: "Match metadata first, then choose the best source video."
                        color: root.secondaryText
                        font.pixelSize: 11
                    }
                    Text {
                        visible: !root.searchPanelExpanded
                        Layout.fillWidth: true
                        text: titleField.text
                              + (artistField.text ? " · " + artistField.text : "")
                              + (albumField.text ? " · " + albumField.text : "")
                        color: root.secondaryText
                        font.pixelSize: 11
                        elide: Text.ElideRight
                    }
                    Item {
                        visible: root.searchPanelExpanded
                        Layout.fillWidth: true
                    }
                    Text {
                        visible: root.searchPanelExpanded
                        text: "TITLE + ARTIST REQUIRED"
                        color: root.cyan
                        font.pixelSize: 9
                        font.letterSpacing: 0.7
                    }
                    Button {
                        objectName: "recordingSearchPanelToggle"
                        text: root.searchPanelExpanded ? "Hide" : "Edit search"
                        flat: true
                        enabled: !odysseus.busy
                        Layout.preferredHeight: 30
                        onClicked: root.searchPanelExpanded = !root.searchPanelExpanded
                    }
                }
                RowLayout {
                    objectName: "recordingSearchFields"
                    visible: root.searchPanelExpanded
                    Layout.fillWidth: true
                    spacing: 10
                    TextField {
                        id: titleField
                        Layout.fillWidth: true
                        Layout.preferredWidth: 240
                        Layout.preferredHeight: 36
                        placeholderText: "Recording title"
                        enabled: !odysseus.busy
                        onAccepted: searchButton.clicked()
                    }
                    TextField {
                        id: artistField
                        Layout.fillWidth: true
                        Layout.preferredWidth: 220
                        Layout.preferredHeight: 36
                        placeholderText: "Artist"
                        enabled: !odysseus.busy
                        onAccepted: searchButton.clicked()
                    }
                    TextField {
                        id: albumField
                        Layout.fillWidth: true
                        Layout.preferredWidth: 180
                        Layout.preferredHeight: 36
                        placeholderText: "Album · optional"
                        enabled: !odysseus.busy
                        onAccepted: searchButton.clicked()
                    }
                    TextField {
                        id: yearField
                        Layout.preferredWidth: 96
                        Layout.preferredHeight: 36
                        placeholderText: "Year"
                        inputMethodHints: Qt.ImhDigitsOnly
                        enabled: !odysseus.busy
                        onAccepted: searchButton.clicked()
                    }
                    Button {
                        id: searchButton
                        text: odysseus.busy ? "Searching…" : "Search"
                        highlighted: true
                        enabled: !odysseus.busy
                        Layout.preferredWidth: 112
                        Layout.preferredHeight: 36
                        onClicked: {
                            if (titleField.text.trim().length > 0
                                    && artistField.text.trim().length > 0)
                                root.searchPanelExpanded = false
                            odysseus.searchRecordings(
                                titleField.text,
                                artistField.text,
                                albumField.text,
                                yearField.text
                            )
                        }
                    }
                }
            }
        }

        Rectangle {
            objectName: "catalogSearchPanel"
            visible: root.uiMode !== "recording"
            Layout.fillWidth: true
            implicitHeight: root.searchPanelExpanded ? 174 : 58
            radius: 16
            color: root.panelColor
            border.color: root.borderColor
            Behavior on implicitHeight { NumberAnimation { duration: 160 } }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 18
                spacing: 10
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: root.uiMode === "release"
                              ? "Find a full release" : "Browse an artist’s catalog"
                        color: root.primaryText
                        font.pixelSize: 16
                        font.bold: true
                    }
                    Text {
                        visible: root.searchPanelExpanded
                        text: root.uiMode === "release"
                              ? "Search releases, inspect tracks, then queue your selection."
                              : "Explore albums, EPs, singles, live releases, and compilations."
                        color: root.secondaryText
                        font.pixelSize: 11
                    }
                    Text {
                        visible: !root.searchPanelExpanded
                        Layout.fillWidth: true
                        text: (root.uiMode === "release" && catalogAlbumField.text
                               ? catalogAlbumField.text + " · " : "")
                              + catalogArtistField.text
                              + (releaseTypePicker.currentText
                                 ? " · " + releaseTypePicker.currentText : "")
                        color: root.secondaryText
                        font.pixelSize: 11
                        elide: Text.ElideRight
                    }
                    Item {
                        visible: root.searchPanelExpanded
                        Layout.fillWidth: true
                    }
                    Button {
                        objectName: "catalogSearchPanelToggle"
                        text: root.searchPanelExpanded ? "Hide" : "Edit search"
                        flat: true
                        enabled: !odysseus.busy
                        Layout.preferredHeight: 30
                        onClicked: root.searchPanelExpanded = !root.searchPanelExpanded
                    }
                }
                RowLayout {
                    objectName: "catalogSearchFields"
                    visible: root.searchPanelExpanded
                    Layout.fillWidth: true
                    spacing: 12
                    TextField {
                        id: catalogAlbumField
                        visible: root.uiMode === "release"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 36
                        placeholderText: "Album title *"
                        enabled: !odysseus.busy
                        onAccepted: catalogSearchButton.clicked()
                    }
                    TextField {
                        id: catalogArtistField
                        Layout.fillWidth: true
                        Layout.preferredHeight: 36
                        placeholderText: "Artist *"
                        enabled: !odysseus.busy
                        onAccepted: catalogSearchButton.clicked()
                    }
                    TextField {
                        id: catalogYearField
                        Layout.preferredWidth: 100
                        Layout.preferredHeight: 36
                        placeholderText: "Exact year"
                        inputMethodHints: Qt.ImhDigitsOnly
                        enabled: !odysseus.busy && !yearRangeEnabled.checked
                        onAccepted: catalogSearchButton.clicked()
                    }
                    ComboBox {
                        id: releaseTypePicker
                        Layout.preferredWidth: 140
                        Layout.preferredHeight: 36
                        model: ["", "Album", "Single", "EP", "Compilation", "Live"]
                        displayText: currentText || "Any type"
                        enabled: !odysseus.busy
                    }
                    CheckBox {
                        id: compilationCheck
                        visible: root.uiMode === "discography"
                        text: "Compilations"
                        enabled: !odysseus.busy
                    }
                    Button {
                        id: catalogSearchButton
                        text: odysseus.busy ? "Searching…"
                              : root.uiMode === "release" ? "Find album" : "Browse"
                        highlighted: true
                        enabled: !odysseus.busy
                        Layout.preferredHeight: 36
                        onClicked: {
                            discographyFilterField.clear()
                            if (catalogArtistField.text.trim().length > 0
                                    && (root.uiMode !== "release"
                                        || catalogAlbumField.text.trim().length > 0))
                                root.searchPanelExpanded = false
                            let yearFrom = yearRangeEnabled.checked
                                           ? Math.round(yearRange.first.value).toString() : ""
                            let yearTo = yearRangeEnabled.checked
                                         ? Math.round(yearRange.second.value).toString() : ""
                            if (root.uiMode === "release") {
                                odysseus.searchAlbums(
                                    catalogAlbumField.text,
                                    catalogArtistField.text,
                                    yearRangeEnabled.checked ? "" : catalogYearField.text,
                                    releaseTypePicker.currentText,
                                    yearFrom,
                                    yearTo
                                )
                            } else {
                                odysseus.searchDiscography(
                                    catalogArtistField.text,
                                    yearRangeEnabled.checked ? "" : catalogYearField.text,
                                    releaseTypePicker.currentText,
                                    compilationCheck.checked,
                                    yearFrom,
                                    yearTo
                                )
                            }
                        }
                    }
                }
                RowLayout {
                    visible: root.searchPanelExpanded
                    Layout.fillWidth: true
                    spacing: 10
                    Switch {
                        id: yearRangeEnabled
                        text: "Year range"
                        enabled: !odysseus.busy
                    }
                    Rectangle {
                        implicitWidth: 52
                        implicitHeight: 28
                        radius: 8
                        color: yearRangeEnabled.checked ? root.accentSoft : root.panelRaised
                        Text {
                            anchors.centerIn: parent
                            text: Math.round(yearRange.first.value)
                            color: yearRangeEnabled.checked
                                   ? root.primaryText : root.secondaryText
                            font.pixelSize: 11
                            font.bold: yearRangeEnabled.checked
                        }
                    }
                    RangeSlider {
                        id: yearRange
                        Layout.fillWidth: true
                        from: odysseus.minYear
                        to: odysseus.maxYear
                        stepSize: 1
                        snapMode: RangeSlider.SnapAlways
                        enabled: !odysseus.busy && yearRangeEnabled.checked
                        first.value: Math.max(from, 1960)
                        second.value: to
                        first.handle: Rectangle {
                            x: yearRange.leftPadding + yearRange.first.visualPosition
                               * (yearRange.availableWidth - width)
                            y: yearRange.topPadding
                               + yearRange.availableHeight / 2 - height / 2
                            implicitWidth: 18
                            implicitHeight: 18
                            radius: 9
                            color: yearRangeEnabled.checked
                                   ? root.accent : "#66738e"
                            border.color: root.primaryText
                        }
                        second.handle: Rectangle {
                            x: yearRange.leftPadding + yearRange.second.visualPosition
                               * (yearRange.availableWidth - width)
                            y: yearRange.topPadding
                               + yearRange.availableHeight / 2 - height / 2
                            implicitWidth: 18
                            implicitHeight: 18
                            radius: 9
                            color: yearRangeEnabled.checked
                                   ? root.accent : "#66738e"
                            border.color: root.primaryText
                        }
                    }
                    Rectangle {
                        implicitWidth: 52
                        implicitHeight: 28
                        radius: 8
                        color: yearRangeEnabled.checked ? root.accentSoft : root.panelRaised
                        Text {
                            anchors.centerIn: parent
                            text: Math.round(yearRange.second.value)
                            color: yearRangeEnabled.checked
                                   ? root.primaryText : root.secondaryText
                            font.pixelSize: 11
                            font.bold: yearRangeEnabled.checked
                        }
                    }
                }
            }
        }

        Rectangle {
            objectName: "searchStatusPanel"
            visible: root.searchPanelExpanded
                     || odysseus.busy
                     || !root.hasSearchResults
                     || odysseus.statusColor === root.danger
                     || odysseus.statusColor === root.warning
            Layout.fillWidth: true
            implicitHeight: 46
            radius: 12
            color: "#0e1829"
            border.color: root.borderColor
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                spacing: 10
                Rectangle {
                    width: 24
                    height: 24
                    radius: 8
                    color: Qt.rgba(1, 1, 1, 0.04)
                    border.color: odysseus.statusColor
                    Rectangle {
                        anchors.centerIn: parent
                        width: 7
                        height: 7
                        radius: 4
                        color: odysseus.statusColor
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: odysseus.statusText
                    color: odysseus.statusColor
                    elide: Text.ElideRight
                    font.pixelSize: 13
                }
                Text {
                    visible: odysseus.busy
                    text: "WORKING"
                    color: root.cyan
                    font.pixelSize: 9
                    font.bold: true
                    font.letterSpacing: 0.8
                }
            }
        }

        SplitView {
            visible: root.uiMode === "recording"
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal
            handle: Rectangle {
                implicitWidth: 8
                color: SplitHandle.pressed ? root.accent
                      : SplitHandle.hovered ? "#43557a" : root.color
            }

            Rectangle {
                SplitView.preferredWidth: 580
                SplitView.minimumWidth: 400
                radius: 16
                color: root.panelColor
                border.color: root.borderColor

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "Metadata candidates"
                            color: root.primaryText
                            font.pixelSize: 16
                            font.bold: true
                        }
                        Item { Layout.fillWidth: true }
                        Rectangle {
                            implicitWidth: recordingCount.implicitWidth + 16
                            implicitHeight: 24
                            radius: 8
                            color: root.panelRaised
                            Text {
                                id: recordingCount
                                anchors.centerIn: parent
                                text: odysseus.recordingResults.length
                                color: root.cyan
                                font.pixelSize: 11
                                font.bold: true
                            }
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Choose the release metadata that best matches your recording."
                        color: root.secondaryText
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }
                    ListView {
                        id: recordingList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 8
                        clip: true
                        model: odysseus.recordingResults
                        ScrollBar.vertical: ScrollBar { }

                        delegate: Rectangle {
                            property bool selected: index === odysseus.selectedRecordingIndex
                            width: recordingList.width
                            height: 86
                            radius: 12
                            color: selected ? root.accentSoft
                                  : recordingMouse.containsMouse ? root.panelHover
                                  : root.panelRaised
                            border.color: selected ? root.accent : root.borderColor

                            Behavior on color { ColorAnimation { duration: 120 } }

                            Rectangle {
                                visible: parent.selected
                                width: 3
                                height: parent.height - 20
                                radius: 2
                                color: root.cyan
                                anchors.left: parent.left
                                anchors.leftMargin: 4
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            MouseArea {
                                id: recordingMouse
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                hoverEnabled: true
                                enabled: !odysseus.busy
                                onClicked: odysseus.selectRecording(index)
                            }
                            Column {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 4
                                Text {
                                    width: parent.width
                                    text: modelData.title
                                    color: root.primaryText
                                    font.pixelSize: 14
                                    font.bold: true
                                    elide: Text.ElideRight
                                }
                                Text {
                                    width: parent.width
                                    text: modelData.artist + " · " + modelData.album
                                    color: root.secondaryText
                                    font.pixelSize: 12
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: modelData.date + "  ·  " + modelData.source
                                    color: "#71d7ff"
                                    font.pixelSize: 11
                                }
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: recordingList.count === 0
                            text: "Search results will appear here"
                            color: root.secondaryText
                        }
                    }
                }
            }

            Rectangle {
                SplitView.fillWidth: true
                SplitView.minimumWidth: 440
                radius: 16
                color: root.panelColor
                border.color: root.borderColor

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "Video candidates"
                            color: root.primaryText
                            font.pixelSize: 16
                            font.bold: true
                        }
                        Item { Layout.fillWidth: true }
                        Rectangle {
                            implicitWidth: videoCount.implicitWidth + 16
                            implicitHeight: 24
                            radius: 8
                            color: root.panelRaised
                            Text {
                                id: videoCount
                                anchors.centerIn: parent
                                text: odysseus.videoResults.length
                                color: root.cyan
                                font.pixelSize: 11
                                font.bold: true
                            }
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: "Select the source video after reviewing its channel and duration."
                        color: root.secondaryText
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }
                    ListView {
                        id: videoList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 8
                        clip: true
                        model: odysseus.videoResults
                        ScrollBar.vertical: ScrollBar { }

                        delegate: Rectangle {
                            property bool selected: index === odysseus.selectedVideoIndex
                            width: videoList.width
                            height: 86
                            radius: 12
                            color: selected ? root.accentSoft
                                  : videoMouse.containsMouse ? root.panelHover
                                  : root.panelRaised
                            border.color: selected ? root.accent : root.borderColor

                            Behavior on color { ColorAnimation { duration: 120 } }

                            Rectangle {
                                visible: parent.selected
                                width: 3
                                height: parent.height - 20
                                radius: 2
                                color: root.cyan
                                anchors.left: parent.left
                                anchors.leftMargin: 4
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            MouseArea {
                                id: videoMouse
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                hoverEnabled: true
                                enabled: !odysseus.busy
                                onClicked: odysseus.selectVideo(index)
                            }
                            Column {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 5
                                Text {
                                    width: parent.width
                                    text: modelData.title
                                    color: root.primaryText
                                    font.pixelSize: 14
                                    font.bold: true
                                    elide: Text.ElideRight
                                }
                                Text {
                                    width: parent.width
                                    text: modelData.channel
                                    color: root.secondaryText
                                    font.pixelSize: 12
                                    elide: Text.ElideRight
                                }
                                Text {
                                    text: modelData.duration + "  ·  " + modelData.views
                                    color: "#71d7ff"
                                    font.pixelSize: 11
                                }
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: videoList.count === 0
                            text: odysseus.selectedRecordingIndex < 0
                                  ? "Select metadata first" : "Videos will appear here"
                            color: root.secondaryText
                        }
                    }
                }
            }
        }

        SplitView {
            visible: root.uiMode !== "recording"
            Layout.fillWidth: true
            Layout.fillHeight: true
            orientation: Qt.Horizontal
            handle: Rectangle {
                implicitWidth: 8
                color: SplitHandle.pressed ? root.accent
                      : SplitHandle.hovered ? "#43557a" : root.color
            }

            Rectangle {
                SplitView.preferredWidth: 610
                SplitView.minimumWidth: 430
                radius: 16
                color: root.panelColor
                border.color: root.borderColor
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: root.uiMode === "release"
                                  ? "Release candidates" : "Artist discography"
                            color: root.primaryText
                            font.pixelSize: 16
                            font.bold: true
                        }
                        Item { Layout.fillWidth: true }
                        Rectangle {
                            implicitWidth: catalogCount.implicitWidth + 16
                            implicitHeight: 24
                            radius: 8
                            color: root.panelRaised
                            Text {
                                id: catalogCount
                                anchors.centerIn: parent
                                text: root.uiMode === "discography"
                                      && discographyFilterField.text.length > 0
                                      ? odysseus.catalogResults.length + " / "
                                        + odysseus.catalogTotalCount
                                      : odysseus.catalogResults.length
                                color: root.cyan
                                font.pixelSize: 11
                                font.bold: true
                            }
                        }
                    }
                    Text {
                        text: "Select a release to load its complete track listing."
                        color: root.secondaryText
                        font.pixelSize: 12
                    }
                    RowLayout {
                        visible: root.uiMode === "discography"
                                 && odysseus.catalogTotalCount > 8
                        Layout.fillWidth: true
                        spacing: 7
                        TextField {
                            id: discographyFilterField
                            objectName: "discographyFilterField"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 36
                            placeholderText: "Filter by release, year, type, label…"
                            enabled: !odysseus.busy
                            selectByMouse: true
                            onTextChanged: odysseus.filterCatalogResults(text)
                        }
                        Button {
                            text: "Clear"
                            flat: true
                            visible: discographyFilterField.text.length > 0
                            onClicked: discographyFilterField.clear()
                        }
                    }
                    ListView {
                        id: catalogList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 8
                        clip: true
                        model: odysseus.catalogResults
                        ScrollBar.vertical: ScrollBar { }
                        delegate: Rectangle {
                            id: catalogCard
                            property bool selected: index === odysseus.selectedCatalogIndex
                            property color sourceAccent:
                                modelData.source === "Spotify" ? root.success
                              : modelData.source === "Discogs" ? root.warning
                              : modelData.source === "Apple Music" ? "#fa5b78"
                              : modelData.source === "MusicBrainz" ? root.cyan
                              : root.accent
                            width: catalogList.width
                            height: 116
                            radius: 14
                            color: selected ? "#1b2d50"
                                  : catalogMouse.containsMouse ? root.panelHover
                                  : root.panelRaised
                            border.width: selected ? 2 : 1
                            border.color: selected ? root.accent
                                          : catalogMouse.containsMouse
                                            ? sourceAccent : root.borderColor
                            Behavior on color { ColorAnimation { duration: 140 } }
                            Behavior on border.color { ColorAnimation { duration: 140 } }

                            Rectangle {
                                visible: catalogCard.selected
                                width: 4
                                height: parent.height - 24
                                radius: 3
                                color: catalogCard.sourceAccent
                                anchors.left: parent.left
                                anchors.leftMargin: 5
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            MouseArea {
                                id: catalogMouse
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                hoverEnabled: true
                                enabled: !odysseus.busy
                                onClicked: odysseus.selectCatalogRelease(index)
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 650
                                ToolTip.text: modelData.date + " · "
                                              + modelData.type + " · "
                                              + modelData.source
                                              + (modelData.editionDetail
                                                 ? "\n" + modelData.editionDetail : "")
                                              + (modelData.identifierDetail
                                                 ? "\n" + modelData.identifierDetail : "")
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                anchors.leftMargin: catalogCard.selected ? 17 : 12
                                spacing: 12

                                Rectangle {
                                    Layout.preferredWidth: 58
                                    Layout.preferredHeight: 86
                                    radius: 12
                                    color: Qt.rgba(
                                        catalogCard.sourceAccent.r,
                                        catalogCard.sourceAccent.g,
                                        catalogCard.sourceAccent.b,
                                        0.13
                                    )
                                    border.color: Qt.rgba(
                                        catalogCard.sourceAccent.r,
                                        catalogCard.sourceAccent.g,
                                        catalogCard.sourceAccent.b,
                                        0.55
                                    )
                                    clip: true

                                    Image {
                                        id: releaseCover
                                        anchors.fill: parent
                                        anchors.margins: 1
                                        source: modelData.coverArtUrl
                                        asynchronous: true
                                        cache: true
                                        fillMode: Image.PreserveAspectCrop
                                        visible: status === Image.Ready
                                    }

                                    Column {
                                        anchors.centerIn: parent
                                        spacing: 3
                                        visible: releaseCover.status !== Image.Ready
                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            text: modelData.title && modelData.title.length
                                                  ? modelData.title.charAt(0).toUpperCase()
                                                  : "?"
                                            color: catalogCard.sourceAccent
                                            font.pixelSize: 24
                                            font.bold: true
                                        }
                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            text: modelData.year
                                            color: root.primaryText
                                            font.pixelSize: 10
                                            font.bold: true
                                        }
                                    }

                                    Rectangle {
                                        visible: releaseCover.status === Image.Ready
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.bottom: parent.bottom
                                        height: 19
                                        color: Qt.rgba(0.03, 0.05, 0.09, 0.84)
                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData.year
                                            color: "white"
                                            font.pixelSize: 10
                                            font.bold: true
                                        }
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    spacing: 3

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        Text {
                                            Layout.fillWidth: true
                                            text: modelData.title
                                            color: root.primaryText
                                            font.bold: true
                                            font.pixelSize: 14
                                            elide: Text.ElideRight
                                        }
                                        Rectangle {
                                            visible: catalogCard.selected
                                            Layout.preferredWidth: 22
                                            Layout.preferredHeight: 22
                                            radius: 11
                                            color: root.accent
                                            Text {
                                                anchors.centerIn: parent
                                                text: "✓"
                                                color: "white"
                                                font.pixelSize: 12
                                                font.bold: true
                                            }
                                        }
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.artist
                                        color: root.secondaryText
                                        font.pixelSize: 12
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        visible: modelData.editionDetail.length > 0
                                        text: modelData.editionDetail
                                        color: root.secondaryText
                                        font.pixelSize: 10
                                        elide: Text.ElideRight
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 6

                                        Rectangle {
                                            implicitWidth: releaseTypeText.implicitWidth + 14
                                            implicitHeight: 22
                                            radius: 7
                                            color: root.accentSoft
                                            Text {
                                                id: releaseTypeText
                                                anchors.centerIn: parent
                                                text: modelData.type.toUpperCase()
                                                color: root.primaryText
                                                font.pixelSize: 9
                                                font.bold: true
                                                font.letterSpacing: 0.5
                                            }
                                        }

                                        Rectangle {
                                            implicitWidth: releaseSourceText.implicitWidth + 14
                                            implicitHeight: 22
                                            radius: 7
                                            color: Qt.rgba(
                                                catalogCard.sourceAccent.r,
                                                catalogCard.sourceAccent.g,
                                                catalogCard.sourceAccent.b,
                                                0.13
                                            )
                                            border.color: Qt.rgba(
                                                catalogCard.sourceAccent.r,
                                                catalogCard.sourceAccent.g,
                                                catalogCard.sourceAccent.b,
                                                0.42
                                            )
                                            Text {
                                                id: releaseSourceText
                                                anchors.centerIn: parent
                                                text: modelData.source.toUpperCase()
                                                color: catalogCard.sourceAccent
                                                font.pixelSize: 9
                                                font.bold: true
                                                font.letterSpacing: 0.4
                                            }
                                        }

                                        Rectangle {
                                            visible: modelData.isReissue
                                            implicitWidth: editionText.implicitWidth + 14
                                            implicitHeight: 22
                                            radius: 7
                                            color: "#332b20"
                                            border.color: "#665339"
                                            Text {
                                                id: editionText
                                                anchors.centerIn: parent
                                                text: "EDITION " + modelData.editionYear
                                                color: root.warning
                                                font.pixelSize: 9
                                                font.bold: true
                                                font.letterSpacing: 0.4
                                            }
                                        }

                                        Item { Layout.fillWidth: true }
                                        Text {
                                            visible: !modelData.isReissue
                                            text: modelData.yearKind.toUpperCase()
                                            color: root.secondaryText
                                            font.pixelSize: 9
                                            font.letterSpacing: 0.5
                                        }
                                    }
                                }
                            }
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: catalogList.count === 0
                            text: discographyFilterField.text.length > 0
                                  ? "No releases match this filter"
                                  : "Release results will appear here"
                            color: root.secondaryText
                        }
                    }
                }
            }

            Rectangle {
                SplitView.fillWidth: true
                SplitView.minimumWidth: 460
                radius: 16
                color: root.panelColor
                border.color: root.borderColor
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "Tracks"
                            color: root.primaryText
                            font.pixelSize: 16
                            font.bold: true
                        }
                        Rectangle {
                            implicitWidth: selectedTracksText.implicitWidth + 16
                            implicitHeight: 24
                            radius: 8
                            color: root.accentSoft
                            Text {
                                id: selectedTracksText
                                anchors.centerIn: parent
                                text: odysseus.selectedTrackCount + " / "
                                      + odysseus.releaseTracks.length + " selected"
                                color: root.cyan
                                font.pixelSize: 10
                                font.bold: true
                            }
                        }
                        Item { Layout.fillWidth: true }
                        Button {
                            text: "All"
                            flat: true
                            enabled: !odysseus.busy
                            onClicked: odysseus.selectAllTracks(true)
                        }
                        Button {
                            text: "None"
                            flat: true
                            enabled: !odysseus.busy
                            onClicked: odysseus.selectAllTracks(false)
                        }
                    }
                    ListView {
                        id: trackList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 5
                        clip: true
                        model: odysseus.releaseTracks
                        ScrollBar.vertical: ScrollBar { }
                        delegate: Rectangle {
                            width: trackList.width
                            height: 52
                            radius: 10
                            color: modelData.selected ? "#192a45" : root.panelRaised
                            border.color: modelData.selected ? "#304e78" : root.borderColor
                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 8
                                anchors.rightMargin: 12
                                CheckBox {
                                    id: trackCheck
                                    checked: modelData.selected
                                    indicator: Rectangle {
                                        implicitWidth: 20
                                        implicitHeight: 20
                                        x: trackCheck.leftPadding
                                        y: parent.height / 2 - height / 2
                                        radius: 5
                                        color: trackCheck.checked ? root.accent : root.panelColor
                                        border.color: trackCheck.checked
                                                      ? root.accent : root.secondaryText
                                        Text {
                                            anchors.centerIn: parent
                                            text: trackCheck.checked ? "✓" : ""
                                            color: "white"
                                            font.bold: true
                                        }
                                    }
                                    onClicked: odysseus.toggleTrack(index)
                                }
                                Text {
                                    text: modelData.position
                                    color: "#71d7ff"
                                    Layout.preferredWidth: 28
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0
                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.title
                                        color: root.primaryText
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        Layout.fillWidth: true
                                        text: modelData.artist
                                        color: root.secondaryText
                                        font.pixelSize: 10
                                        elide: Text.ElideRight
                                    }
                                }
                                Text {
                                    text: modelData.duration
                                    color: root.secondaryText
                                }
                            }
                        }
                        Text {
                            anchors.centerIn: parent
                            visible: trackList.count === 0
                            text: "Select a release to load tracks"
                            color: root.secondaryText
                        }
                    }
                }
            }
        }

        Rectangle {
            visible: root.uiMode === "recording"
            Layout.fillWidth: true
            implicitHeight: 88
            radius: 16
            color: root.panelColor
            border.color: root.borderColor

            RowLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 12
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: odysseus.downloading
                                  ? "Download in progress" : "Recording download"
                            color: root.primaryText
                            font.pixelSize: 11
                            font.bold: true
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            visible: odysseus.downloading && odysseus.downloadProgress > 0
                            text: Math.round(odysseus.downloadProgress) + "%"
                            color: root.cyan
                            font.pixelSize: 11
                            font.bold: true
                        }
                    }
                    ProgressBar {
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        value: odysseus.downloadProgress
                    }
                    Text {
                        Layout.fillWidth: true
                        text: odysseus.progressDetail || "No active download"
                        color: root.secondaryText
                        font.pixelSize: 11
                        elide: Text.ElideMiddle
                    }
                }
                ComboBox {
                    id: qualityPicker
                    model: ["audio", "best", "worst"]
                    enabled: !odysseus.busy
                    Layout.preferredWidth: 105
                    ToolTip.visible: hovered
                    ToolTip.text: "Output quality"
                }
                Button {
                    text: "Cancel"
                    visible: odysseus.downloading
                    onClicked: odysseus.cancelDownload()
                }
                Button {
                    text: "Reveal file"
                    visible: odysseus.hasLastDownload
                    enabled: !odysseus.busy
                    onClicked: odysseus.revealLastDownload()
                }
                Button {
                    text: "Add to queue"
                    highlighted: true
                    enabled: odysseus.canDownload
                    Layout.preferredWidth: 128
                    onClicked: odysseus.downloadSelected(qualityPicker.currentText)
                }
            }
        }

        Rectangle {
            visible: root.uiMode !== "recording"
            Layout.fillWidth: true
            implicitHeight: 88
            radius: 16
            color: root.panelColor
            border.color: root.borderColor
            RowLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 12
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: odysseus.downloading
                                  ? "Release download in progress" : "Release download"
                            color: root.primaryText
                            font.pixelSize: 11
                            font.bold: true
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            visible: odysseus.downloading && odysseus.downloadProgress > 0
                            text: Math.round(odysseus.downloadProgress) + "%"
                            color: root.cyan
                            font.pixelSize: 11
                            font.bold: true
                        }
                    }
                    ProgressBar {
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        value: odysseus.downloadProgress
                        indeterminate: odysseus.downloading
                                       && odysseus.downloadProgress === 0
                    }
                    Text {
                        Layout.fillWidth: true
                        text: odysseus.progressDetail || "No active release download"
                        color: root.secondaryText
                        elide: Text.ElideMiddle
                        font.pixelSize: 11
                    }
                }
                ComboBox {
                    id: releaseQualityPicker
                    model: ["audio", "best", "worst"]
                    enabled: !odysseus.busy
                    Layout.preferredWidth: 105
                    ToolTip.visible: hovered
                    ToolTip.text: "Output quality"
                }
                SpinBox {
                    id: jobsPicker
                    from: 1
                    to: 4
                    value: 1
                    editable: true
                    enabled: !odysseus.busy
                    ToolTip.visible: hovered
                    ToolTip.text: "Parallel jobs"
                }
                Button {
                    text: "Cancel"
                    visible: odysseus.downloading
                    onClicked: odysseus.cancelDownload()
                }
                Button {
                    text: "Add tracks to queue"
                    highlighted: true
                    enabled: odysseus.canDownloadRelease
                    onClicked: odysseus.downloadSelectedRelease(
                        releaseQualityPicker.currentText,
                        jobsPicker.value
                    )
                }
            }
        }
    }
}
