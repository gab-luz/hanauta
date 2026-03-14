#define _POSIX_C_SOURCE 200809L

#include <gio/gio.h>
#include <glib.h>
#include <gtk/gtk.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>

typedef struct {
    gchar *key;
    gchar *label;
} ActionEntry;

typedef struct {
    guint id;
    gchar *app_name;
    gchar *summary;
    gchar *body;
    gint expire_timeout;
    GPtrArray *actions;
} NotificationPayload;

typedef struct {
    guint id;
    gchar *app_name;
    gchar *summary;
    gchar *body;
    gint64 timestamp;
} HistoryEntry;

typedef struct {
    GtkWidget *window;
    guint timeout_id;
    guint id;
} ToastWindow;

typedef struct {
    GtkApplication *app;
    GDBusConnection *connection;
    guint owner_id;
    guint registration_id;
    GHashTable *toasts;
    GPtrArray *history;
    guint next_id;
} NotifyDaemon;

static NotifyDaemon g_daemon = {0};

typedef struct {
    gboolean use_matugen;
    gchar primary[8];
    gchar on_primary[8];
    gchar primary_container[8];
    gchar on_primary_container[8];
    gchar surface_container[8];
    gchar surface_container_high[8];
    gchar on_surface[8];
    gchar on_surface_variant[8];
    gchar outline[8];
} ThemePalette;

static const gchar *INTROSPECTION_XML =
    "<node>"
    "  <interface name='org.freedesktop.Notifications'>"
    "    <method name='GetCapabilities'>"
    "      <arg type='as' name='caps' direction='out'/>"
    "    </method>"
    "    <method name='GetServerInformation'>"
    "      <arg type='s' name='name' direction='out'/>"
    "      <arg type='s' name='vendor' direction='out'/>"
    "      <arg type='s' name='version' direction='out'/>"
    "      <arg type='s' name='spec_version' direction='out'/>"
    "    </method>"
    "    <method name='Notify'>"
    "      <arg type='s' name='app_name' direction='in'/>"
    "      <arg type='u' name='replaces_id' direction='in'/>"
    "      <arg type='s' name='app_icon' direction='in'/>"
    "      <arg type='s' name='summary' direction='in'/>"
    "      <arg type='s' name='body' direction='in'/>"
    "      <arg type='as' name='actions' direction='in'/>"
    "      <arg type='a{sv}' name='hints' direction='in'/>"
    "      <arg type='i' name='expire_timeout' direction='in'/>"
    "      <arg type='u' name='id' direction='out'/>"
    "    </method>"
    "    <method name='CloseNotification'>"
    "      <arg type='u' name='id' direction='in'/>"
    "    </method>"
    "    <signal name='NotificationClosed'>"
    "      <arg type='u' name='id'/>"
    "      <arg type='u' name='reason'/>"
    "    </signal>"
    "    <signal name='ActionInvoked'>"
    "      <arg type='u' name='id'/>"
    "      <arg type='s' name='action_key'/>"
    "    </signal>"
    "  </interface>"
    "</node>";

static void theme_palette_defaults(ThemePalette *theme) {
    theme->use_matugen = FALSE;
    g_strlcpy(theme->primary, "#D0BCFF", sizeof(theme->primary));
    g_strlcpy(theme->on_primary, "#381E72", sizeof(theme->on_primary));
    g_strlcpy(theme->primary_container, "#4F378B", sizeof(theme->primary_container));
    g_strlcpy(theme->on_primary_container, "#EADDFF", sizeof(theme->on_primary_container));
    g_strlcpy(theme->surface_container, "#211F26", sizeof(theme->surface_container));
    g_strlcpy(theme->surface_container_high, "#2B2930", sizeof(theme->surface_container_high));
    g_strlcpy(theme->on_surface, "#E6E0E9", sizeof(theme->on_surface));
    g_strlcpy(theme->on_surface_variant, "#CAC4D0", sizeof(theme->on_surface_variant));
    g_strlcpy(theme->outline, "#938F99", sizeof(theme->outline));
}

static gboolean valid_hex_color(const gchar *text) {
    if (text == NULL || text[0] != '#' || strlen(text) != 7) {
        return FALSE;
    }
    for (gsize i = 1; i < 7; ++i) {
        if (!g_ascii_isxdigit(text[i])) {
            return FALSE;
        }
    }
    return TRUE;
}

static void copy_hex_color(gchar dest[8], const gchar *value, const gchar *fallback) {
    if (valid_hex_color(value)) {
        g_strlcpy(dest, value, 8);
    } else {
        g_strlcpy(dest, fallback, 8);
    }
}

static gchar *theme_file_path(void) {
    return g_build_filename(g_get_home_dir(), ".local", "state", "hanauta", "theme", "pyqt_palette.json", NULL);
}

static gchar *json_string_value(const gchar *json, const gchar *key) {
    gchar *pattern = g_strdup_printf("\"%s\"", key);
    const gchar *found = g_strstr_len(json, -1, pattern);
    const gchar *cursor = NULL;
    GString *value = NULL;
    gboolean escaped = FALSE;
    gchar *result = NULL;
    g_free(pattern);
    if (found == NULL) {
        return NULL;
    }
    cursor = strchr(found, ':');
    if (cursor == NULL) {
        return NULL;
    }
    cursor += 1;
    while (*cursor == ' ' || *cursor == '\t' || *cursor == '\r' || *cursor == '\n') {
        cursor += 1;
    }
    if (*cursor != '"') {
        return NULL;
    }
    cursor += 1;
    value = g_string_new("");
    while (*cursor != '\0') {
        if (escaped) {
            g_string_append_c(value, *cursor);
            escaped = FALSE;
        } else if (*cursor == '\\') {
            escaped = TRUE;
        } else if (*cursor == '"') {
            break;
        } else {
            g_string_append_c(value, *cursor);
        }
        cursor += 1;
    }
    result = g_string_free(value, FALSE);
    return result;
}

static gboolean json_bool_value(const gchar *json, const gchar *key, gboolean fallback) {
    gchar *pattern = g_strdup_printf("\"%s\"", key);
    const gchar *found = g_strstr_len(json, -1, pattern);
    const gchar *cursor = NULL;
    gboolean result = fallback;
    g_free(pattern);
    if (found == NULL) {
        return fallback;
    }
    cursor = strchr(found, ':');
    if (cursor == NULL) {
        return fallback;
    }
    cursor += 1;
    while (*cursor == ' ' || *cursor == '\t' || *cursor == '\r' || *cursor == '\n') {
        cursor += 1;
    }
    if (g_str_has_prefix(cursor, "true")) {
        result = TRUE;
    } else if (g_str_has_prefix(cursor, "false")) {
        result = FALSE;
    }
    return result;
}

static gchar *hex_to_rgba(const gchar *hex, gdouble alpha) {
    guint red = 0;
    guint green = 0;
    guint blue = 0;
    gchar component[3] = {0};
    gdouble clamped = CLAMP(alpha, 0.0, 1.0);
    if (!valid_hex_color(hex)) {
        hex = "#000000";
    }
    component[0] = hex[1];
    component[1] = hex[2];
    red = (guint)strtoul(component, NULL, 16);
    component[0] = hex[3];
    component[1] = hex[4];
    green = (guint)strtoul(component, NULL, 16);
    component[0] = hex[5];
    component[1] = hex[6];
    blue = (guint)strtoul(component, NULL, 16);
    return g_strdup_printf("rgba(%u,%u,%u,%.2f)", red, green, blue, clamped);
}

static void load_theme_palette(ThemePalette *theme) {
    gchar *path = theme_file_path();
    gchar *contents = NULL;
    gchar *value = NULL;
    theme_palette_defaults(theme);
    if (!g_file_get_contents(path, &contents, NULL, NULL) || contents == NULL) {
        g_free(path);
        g_free(contents);
        return;
    }
    theme->use_matugen = json_bool_value(contents, "use_matugen", FALSE);
    if (!theme->use_matugen) {
        g_free(path);
        g_free(contents);
        return;
    }
    value = json_string_value(contents, "primary");
    copy_hex_color(theme->primary, value, theme->primary);
    g_free(value);
    value = json_string_value(contents, "on_primary");
    copy_hex_color(theme->on_primary, value, theme->on_primary);
    g_free(value);
    value = json_string_value(contents, "primary_container");
    copy_hex_color(theme->primary_container, value, theme->primary_container);
    g_free(value);
    value = json_string_value(contents, "on_primary_container");
    copy_hex_color(theme->on_primary_container, value, theme->on_primary_container);
    g_free(value);
    value = json_string_value(contents, "surface_container");
    copy_hex_color(theme->surface_container, value, theme->surface_container);
    g_free(value);
    value = json_string_value(contents, "surface_container_high");
    copy_hex_color(theme->surface_container_high, value, theme->surface_container_high);
    g_free(value);
    value = json_string_value(contents, "on_surface");
    copy_hex_color(theme->on_surface, value, theme->on_surface);
    g_free(value);
    value = json_string_value(contents, "on_surface_variant");
    copy_hex_color(theme->on_surface_variant, value, theme->on_surface_variant);
    g_free(value);
    value = json_string_value(contents, "outline");
    copy_hex_color(theme->outline, value, theme->outline);
    g_free(value);
    g_free(path);
    g_free(contents);
}

static gchar *state_dir_path(void) {
    return g_build_filename(g_get_home_dir(), ".local", "state", "hanauta", "notification-daemon", NULL);
}

static gchar *history_file_path(void) {
    gchar *dir = state_dir_path();
    gchar *path = g_build_filename(dir, "history.json", NULL);
    g_free(dir);
    return path;
}

static gchar *control_file_path(void) {
    gchar *dir = state_dir_path();
    gchar *path = g_build_filename(dir, "control.json", NULL);
    g_free(dir);
    return path;
}

static void ensure_state_dir(void) {
    gchar *dir = state_dir_path();
    g_mkdir_with_parents(dir, 0755);
    g_free(dir);
}

static gboolean is_paused(void) {
    gchar *path = control_file_path();
    gchar *contents = NULL;
    gsize length = 0;
    gboolean paused = FALSE;
    if (g_file_get_contents(path, &contents, &length, NULL) && contents != NULL) {
        paused = strstr(contents, "true") != NULL;
    }
    g_free(contents);
    g_free(path);
    return paused;
}

static void ensure_control_file(void) {
    GError *error = NULL;
    gchar *path = control_file_path();
    if (!g_file_test(path, G_FILE_TEST_EXISTS)) {
        ensure_state_dir();
        g_file_set_contents(path, "{\n  \"paused\": false\n}\n", -1, &error);
        g_clear_error(&error);
    }
    g_free(path);
}

static void action_entry_free(gpointer data) {
    ActionEntry *entry = data;
    if (entry == NULL) {
        return;
    }
    g_free(entry->key);
    g_free(entry->label);
    g_free(entry);
}

static void payload_free(NotificationPayload *payload) {
    if (payload == NULL) {
        return;
    }
    g_free(payload->app_name);
    g_free(payload->summary);
    g_free(payload->body);
    if (payload->actions != NULL) {
        g_ptr_array_free(payload->actions, TRUE);
    }
    g_free(payload);
}

static void history_entry_free(gpointer data) {
    HistoryEntry *entry = data;
    if (entry == NULL) {
        return;
    }
    g_free(entry->app_name);
    g_free(entry->summary);
    g_free(entry->body);
    g_free(entry);
}

static void toast_window_free(gpointer data) {
    ToastWindow *toast = data;
    if (toast == NULL) {
        return;
    }
    if (toast->timeout_id != 0) {
        g_source_remove(toast->timeout_id);
    }
    g_free(toast);
}

static gchar *json_escape(const gchar *text) {
    gchar *escaped = g_strescape(text != NULL ? text : "", NULL);
    gchar *quoted = g_strdup_printf("\"%s\"", escaped != NULL ? escaped : "");
    g_free(escaped);
    return quoted;
}

static void save_history(void) {
    gchar *path = history_file_path();
    GString *json = g_string_new("{\n  \"data\": [\n    [\n");
    for (guint i = 0; i < g_daemon.history->len; ++i) {
        const HistoryEntry *entry = g_ptr_array_index(g_daemon.history, i);
        gchar *app = json_escape(entry->app_name);
        gchar *summary = json_escape(entry->summary);
        gchar *body = json_escape(entry->body);
        g_string_append_printf(
            json,
            "      {\"appname\":{\"data\":%s},\"summary\":{\"data\":%s},\"body\":{\"data\":%s},\"id\":{\"data\":%u},\"timestamp\":{\"data\":%" G_GINT64_FORMAT "}}%s\n",
            app,
            summary,
            body,
            entry->id,
            entry->timestamp,
            (i + 1 < g_daemon.history->len) ? "," : ""
        );
        g_free(app);
        g_free(summary);
        g_free(body);
    }
    g_string_append(json, "    ]\n  ]\n}\n");
    ensure_state_dir();
    g_file_set_contents(path, json->str, -1, NULL);
    g_string_free(json, TRUE);
    g_free(path);
}

static void append_history(const NotificationPayload *payload) {
    HistoryEntry *entry = g_new0(HistoryEntry, 1);
    entry->id = payload->id;
    entry->app_name = g_strdup(payload->app_name);
    entry->summary = g_strdup(payload->summary);
    entry->body = g_strdup(payload->body);
    entry->timestamp = g_get_real_time() / G_USEC_PER_SEC;
    g_ptr_array_add(g_daemon.history, entry);
    while (g_daemon.history->len > 80) {
        g_ptr_array_remove_index(g_daemon.history, 0);
    }
    save_history();
}

static void emit_closed(guint id, guint reason) {
    if (g_daemon.connection == NULL) {
        return;
    }
    g_dbus_connection_emit_signal(
        g_daemon.connection,
        NULL,
        "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications",
        "NotificationClosed",
        g_variant_new("(uu)", id, reason),
        NULL
    );
}

static void emit_action(guint id, const gchar *action_key) {
    if (g_daemon.connection == NULL) {
        return;
    }
    g_dbus_connection_emit_signal(
        g_daemon.connection,
        NULL,
        "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications",
        "ActionInvoked",
        g_variant_new("(us)", id, action_key != NULL ? action_key : "default"),
        NULL
    );
}

static gint compare_toast_windows(gconstpointer a, gconstpointer b) {
    const ToastWindow *left = a;
    const ToastWindow *right = b;
    if (left->id < right->id) {
        return -1;
    }
    if (left->id > right->id) {
        return 1;
    }
    return 0;
}

static void reposition_toasts(void) {
    GdkDisplay *display = gdk_display_get_default();
    GdkMonitor *monitor = NULL;
    GdkRectangle geometry = {0};
    if (display == NULL) {
        return;
    }
    monitor = gdk_display_get_primary_monitor(display);
    if (monitor == NULL) {
        return;
    }
    gdk_monitor_get_geometry(monitor, &geometry);
    gint y = 56;
    GHashTableIter iter;
    gpointer key = NULL;
    gpointer value = NULL;
    GList *ordered = NULL;
    g_hash_table_iter_init(&iter, g_daemon.toasts);
    while (g_hash_table_iter_next(&iter, &key, &value)) {
        ordered = g_list_prepend(ordered, value);
    }
    ordered = g_list_sort(ordered, compare_toast_windows);
    for (GList *node = ordered; node != NULL; node = node->next) {
        ToastWindow *toast = node->data;
        gint toast_width = 356;
        gint toast_height = 120;
        gtk_widget_show_all(toast->window);
        gtk_window_get_size(GTK_WINDOW(toast->window), &toast_width, &toast_height);
        gtk_window_move(GTK_WINDOW(toast->window), geometry.x + geometry.width - toast_width - 24, geometry.y + y);
        y += toast_height + 10;
    }
    g_list_free(ordered);
}

static void dismiss_toast(guint id, guint reason) {
    ToastWindow *toast = g_hash_table_lookup(g_daemon.toasts, GUINT_TO_POINTER(id));
    if (toast == NULL) {
        return;
    }
    GtkWidget *window = toast->window;
    g_hash_table_remove(g_daemon.toasts, GUINT_TO_POINTER(id));
    if (GTK_IS_WIDGET(window)) {
        gtk_widget_destroy(window);
    }
    reposition_toasts();
    emit_closed(id, reason);
}

static gboolean toast_timeout_cb(gpointer user_data) {
    guint id = GPOINTER_TO_UINT(user_data);
    dismiss_toast(id, 1);
    return G_SOURCE_REMOVE;
}

static void close_button_clicked(GtkButton *button, gpointer user_data) {
    (void)button;
    guint id = GPOINTER_TO_UINT(user_data);
    dismiss_toast(id, 2);
}

static void action_button_clicked(GtkButton *button, gpointer user_data) {
    guint id = GPOINTER_TO_UINT(user_data);
    const gchar *action_key = g_object_get_data(G_OBJECT(button), "action-key");
    emit_action(id, action_key);
    dismiss_toast(id, 2);
}

static GtkWidget *make_label(const gchar *name, const gchar *text, gdouble xalign) {
    GtkWidget *label = gtk_label_new(text != NULL ? text : "");
    gtk_widget_set_name(label, name);
    gtk_label_set_xalign(GTK_LABEL(label), (gfloat)xalign);
    gtk_label_set_line_wrap(GTK_LABEL(label), TRUE);
    gtk_label_set_line_wrap_mode(GTK_LABEL(label), PANGO_WRAP_WORD_CHAR);
    return label;
}

static void show_toast(const NotificationPayload *payload) {
    ThemePalette theme;
    GtkWidget *window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_decorated(GTK_WINDOW(window), FALSE);
    gtk_window_set_skip_taskbar_hint(GTK_WINDOW(window), TRUE);
    gtk_window_set_skip_pager_hint(GTK_WINDOW(window), TRUE);
    gtk_window_set_keep_above(GTK_WINDOW(window), TRUE);
    gtk_window_set_accept_focus(GTK_WINDOW(window), FALSE);
    gtk_window_set_resizable(GTK_WINDOW(window), FALSE);
    gtk_window_set_default_size(GTK_WINDOW(window), 356, -1);
    gtk_widget_set_name(window, "hanauta-toast-window");

    GtkWidget *outer = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_container_add(GTK_CONTAINER(window), outer);

    GtkWidget *card = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_widget_set_name(card, "card");
    gtk_container_set_border_width(GTK_CONTAINER(card), 16);
    gtk_box_pack_start(GTK_BOX(outer), card, TRUE, TRUE, 0);

    GtkWidget *top = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    gtk_box_pack_start(GTK_BOX(card), top, FALSE, FALSE, 0);

    GtkWidget *app_name = make_label("appLabel", payload->app_name[0] != '\0' ? payload->app_name : "Notification", 0.0);
    gtk_box_pack_start(GTK_BOX(top), app_name, TRUE, TRUE, 0);

    GtkWidget *close_button = gtk_button_new_with_label("×");
    gtk_widget_set_name(close_button, "closeButton");
    g_signal_connect(close_button, "clicked", G_CALLBACK(close_button_clicked), GUINT_TO_POINTER(payload->id));
    gtk_box_pack_end(GTK_BOX(top), close_button, FALSE, FALSE, 0);

    GtkWidget *summary = make_label("summaryLabel", payload->summary, 0.0);
    gtk_box_pack_start(GTK_BOX(card), summary, FALSE, FALSE, 0);

    if (payload->body != NULL && payload->body[0] != '\0') {
        GtkWidget *body = make_label("bodyLabel", payload->body, 0.0);
        gtk_box_pack_start(GTK_BOX(card), body, FALSE, FALSE, 0);
    }

    if (payload->actions != NULL && payload->actions->len > 0) {
        GtkWidget *actions_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
        gtk_box_pack_start(GTK_BOX(card), actions_box, FALSE, FALSE, 0);
        for (guint i = 0; i < payload->actions->len; ++i) {
            ActionEntry *action = g_ptr_array_index(payload->actions, i);
            GtkWidget *button = gtk_button_new_with_label(action->label != NULL ? action->label : "Action");
            gtk_widget_set_name(button, "actionButton");
            g_object_set_data_full(G_OBJECT(button), "action-key", g_strdup(action->key), g_free);
            g_signal_connect(button, "clicked", G_CALLBACK(action_button_clicked), GUINT_TO_POINTER(payload->id));
            gtk_box_pack_start(GTK_BOX(actions_box), button, FALSE, FALSE, 0);
        }
    }

    load_theme_palette(&theme);
    gchar *card_bg = hex_to_rgba(theme.surface_container, 0.94);
    gchar *card_border = hex_to_rgba(theme.outline, 0.18);
    gchar *app_label = g_strdup(theme.primary);
    gchar *summary_color = g_strdup(theme.on_surface);
    gchar *body_color = hex_to_rgba(theme.on_surface_variant, 0.78);
    gchar *close_bg = hex_to_rgba(theme.on_surface, 0.08);
    gchar *close_fg = g_strdup(theme.on_surface);
    gchar *action_bg = g_strdup(theme.primary);
    gchar *action_fg = g_strdup(theme.on_primary);
    gchar *action_hover = g_strdup(theme.primary_container);
    gchar *action_hover_fg = g_strdup(theme.on_primary_container);

    GtkCssProvider *provider = gtk_css_provider_new();
    gchar *css = g_strdup_printf(
        "#hanauta-toast-window { background: transparent; }"
        "#card { background: %s; border: 1px solid %s; border-radius: 24px; }"
        "#appLabel { color: %s; font-weight: 800; letter-spacing: 0.4px; }"
        "#summaryLabel { color: %s; font-weight: 800; font-size: 15px; }"
        "#bodyLabel { color: %s; }"
        "#closeButton { background: %s; color: %s; border-radius: 12px; padding: 2px 8px; border: none; }"
        "#actionButton { background: %s; color: %s; border-radius: 16px; padding: 7px 13px; border: none; font-weight: 800; }"
        "#actionButton:hover { background: %s; color: %s; }",
        card_bg,
        card_border,
        app_label,
        summary_color,
        body_color,
        close_bg,
        close_fg,
        action_bg,
        action_fg,
        action_hover,
        action_hover_fg
    );
    gtk_css_provider_load_from_data(provider, css, -1, NULL);
    GtkStyleContext *context = gtk_widget_get_style_context(window);
    gtk_style_context_add_provider(context, GTK_STYLE_PROVIDER(provider), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    gtk_style_context_add_provider_for_screen(
        gdk_screen_get_default(),
        GTK_STYLE_PROVIDER(provider),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION
    );
    g_object_unref(provider);
    g_free(card_bg);
    g_free(card_border);
    g_free(app_label);
    g_free(summary_color);
    g_free(body_color);
    g_free(close_bg);
    g_free(close_fg);
    g_free(action_bg);
    g_free(action_fg);
    g_free(action_hover);
    g_free(action_hover_fg);
    g_free(css);

    ToastWindow *toast = g_new0(ToastWindow, 1);
    toast->window = window;
    toast->id = payload->id;
    toast->timeout_id = g_timeout_add(payload->expire_timeout > 0 ? (guint)payload->expire_timeout : 5000, toast_timeout_cb, GUINT_TO_POINTER(payload->id));
    g_hash_table_insert(g_daemon.toasts, GUINT_TO_POINTER(payload->id), toast);
    gtk_widget_show_all(window);
    reposition_toasts();
}

static NotificationPayload *payload_from_variant(GVariant *parameters) {
    NotificationPayload *payload = g_new0(NotificationPayload, 1);
    GVariant *actions_variant = NULL;
    GVariant *hints_variant = NULL;
    const gchar *app_name = "";
    const gchar *app_icon = "";
    const gchar *summary = "";
    const gchar *body = "";
    guint32 replaces_id = 0;
    gint32 expire_timeout = 5000;
    (void)app_icon;

    g_variant_get(
        parameters,
        "(&su&s&s&s@as@a{sv}i)",
        &app_name,
        &replaces_id,
        &app_icon,
        &summary,
        &body,
        &actions_variant,
        &hints_variant,
        &expire_timeout
    );

    payload->id = replaces_id > 0 ? replaces_id : g_daemon.next_id++;
    payload->app_name = g_strdup(app_name);
    payload->summary = g_strdup(summary);
    payload->body = g_strdup(body);
    payload->expire_timeout = expire_timeout;
    payload->actions = g_ptr_array_new_with_free_func(action_entry_free);

    if (actions_variant != NULL) {
        GVariantIter iter;
        const gchar *text = NULL;
        gchar *pending_key = NULL;
        g_variant_iter_init(&iter, actions_variant);
        while (g_variant_iter_next(&iter, "&s", &text)) {
            if (pending_key == NULL) {
                pending_key = g_strdup(text);
            } else {
                ActionEntry *action = g_new0(ActionEntry, 1);
                action->key = pending_key;
                action->label = g_strdup(text);
                g_ptr_array_add(payload->actions, action);
                pending_key = NULL;
            }
        }
        if (pending_key != NULL) {
            ActionEntry *action = g_new0(ActionEntry, 1);
            action->key = pending_key;
            action->label = g_strdup(pending_key);
            g_ptr_array_add(payload->actions, action);
        }
        g_variant_unref(actions_variant);
    }
    if (hints_variant != NULL) {
        g_variant_unref(hints_variant);
    }
    return payload;
}

static void handle_notify(GDBusMethodInvocation *invocation, GVariant *parameters) {
    NotificationPayload *payload = payload_from_variant(parameters);
    append_history(payload);
    if (!is_paused()) {
        dismiss_toast(payload->id, 3);
        show_toast(payload);
    }
    g_dbus_method_invocation_return_value(invocation, g_variant_new("(u)", payload->id));
    payload_free(payload);
}

static void handle_close_notification(GDBusMethodInvocation *invocation, GVariant *parameters) {
    guint32 id = 0;
    g_variant_get(parameters, "(u)", &id);
    dismiss_toast(id, 3);
    g_dbus_method_invocation_return_value(invocation, NULL);
}

static void handle_method_call(
    GDBusConnection *connection,
    const gchar *sender,
    const gchar *object_path,
    const gchar *interface_name,
    const gchar *method_name,
    GVariant *parameters,
    GDBusMethodInvocation *invocation,
    gpointer user_data
) {
    (void)connection;
    (void)sender;
    (void)object_path;
    (void)interface_name;
    (void)user_data;
    if (g_strcmp0(method_name, "GetCapabilities") == 0) {
        const gchar *capabilities[] = {"body", "actions", "persistence", NULL};
        g_dbus_method_invocation_return_value(invocation, g_variant_new("(^as)", capabilities));
        return;
    }
    if (g_strcmp0(method_name, "GetServerInformation") == 0) {
        g_dbus_method_invocation_return_value(invocation, g_variant_new("(ssss)", "Hanauta Notifyd", "Hanauta", "1.0", "1.2"));
        return;
    }
    if (g_strcmp0(method_name, "Notify") == 0) {
        handle_notify(invocation, parameters);
        return;
    }
    if (g_strcmp0(method_name, "CloseNotification") == 0) {
        handle_close_notification(invocation, parameters);
        return;
    }
    g_dbus_method_invocation_return_dbus_error(invocation, "org.freedesktop.Notifications.Error.Failed", "Unknown method.");
}

static const GDBusInterfaceVTable INTERFACE_VTABLE = {
    .method_call = handle_method_call,
};

static void on_bus_acquired(GDBusConnection *connection, const gchar *name, gpointer user_data) {
    (void)name;
    (void)user_data;
    GDBusNodeInfo *introspection = g_dbus_node_info_new_for_xml(INTROSPECTION_XML, NULL);
    g_daemon.connection = g_object_ref(connection);
    g_daemon.registration_id = g_dbus_connection_register_object(
        connection,
        "/org/freedesktop/Notifications",
        introspection->interfaces[0],
        &INTERFACE_VTABLE,
        NULL,
        NULL,
        NULL
    );
    g_dbus_node_info_unref(introspection);
}

static void on_name_lost(GDBusConnection *connection, const gchar *name, gpointer user_data) {
    (void)connection;
    (void)name;
    (void)user_data;
    g_application_quit(G_APPLICATION(g_daemon.app));
}

static void on_activate(GtkApplication *app, gpointer user_data) {
    (void)app;
    (void)user_data;
}

int main(int argc, char **argv) {
    g_daemon.app = gtk_application_new("org.hanauta.Notifyd", G_APPLICATION_NON_UNIQUE);
    g_application_hold(G_APPLICATION(g_daemon.app));
    g_daemon.toasts = g_hash_table_new_full(g_direct_hash, g_direct_equal, NULL, toast_window_free);
    g_daemon.history = g_ptr_array_new_with_free_func(history_entry_free);
    g_daemon.next_id = 1;

    ensure_state_dir();
    ensure_control_file();
    save_history();

    g_signal_connect(g_daemon.app, "activate", G_CALLBACK(on_activate), NULL);
    g_daemon.owner_id = g_bus_own_name(
        G_BUS_TYPE_SESSION,
        "org.freedesktop.Notifications",
        G_BUS_NAME_OWNER_FLAGS_REPLACE,
        on_bus_acquired,
        NULL,
        on_name_lost,
        NULL,
        NULL
    );

    int status = g_application_run(G_APPLICATION(g_daemon.app), argc, argv);

    if (g_daemon.registration_id != 0 && g_daemon.connection != NULL) {
        g_dbus_connection_unregister_object(g_daemon.connection, g_daemon.registration_id);
    }
    if (g_daemon.owner_id != 0) {
        g_bus_unown_name(g_daemon.owner_id);
    }
    g_clear_object(&g_daemon.connection);
    g_ptr_array_free(g_daemon.history, TRUE);
    g_hash_table_destroy(g_daemon.toasts);
    g_clear_object(&g_daemon.app);
    return status;
}
