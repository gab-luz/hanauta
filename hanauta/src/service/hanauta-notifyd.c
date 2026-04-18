#define _POSIX_C_SOURCE 200809L

#include <gio/gio.h>
#include <glib.h>
#include <gtk/gtk.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>

typedef struct {
    gchar *key;
    gchar *action;
    gchar *label;
    gchar *url;
    gchar *method;
    gchar *body;
    gchar *value;
    gboolean clear;
} ActionEntry;

typedef struct {
    guint id;
    gchar *app_name;
    gchar *app_icon;
    gchar *desktop_entry;
    gchar *image_path;
    GdkPixbuf *image_pixbuf;
    guint sender_pid;
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

static gchar *settings_file_path(void);

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

static gint json_int_value(const gchar *json, const gchar *key, gint fallback) {
    gchar *pattern = g_strdup_printf("\"%s\"", key);
    const gchar *found = g_strstr_len(json, -1, pattern);
    const gchar *cursor = NULL;
    gchar *endptr = NULL;
    long parsed = 0;
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
    parsed = strtol(cursor, &endptr, 10);
    if (endptr == cursor || parsed < G_MININT || parsed > G_MAXINT) {
        return fallback;
    }
    return (gint)parsed;
}

static gint load_default_notification_duration_ms(void) {
    gchar *path = settings_file_path();
    gchar *contents = NULL;
    gint value = 10000;
    if (!g_file_get_contents(path, &contents, NULL, NULL) || contents == NULL) {
        g_free(path);
        g_free(contents);
        return 10000;
    }
    value = json_int_value(contents, "default_duration_ms", 10000);
    if (value < 2000) {
        value = 2000;
    } else if (value > 120000) {
        value = 120000;
    }
    g_free(path);
    g_free(contents);
    return value;
}

static gchar *hex_to_rgba(const gchar *hex, gdouble alpha) {
    guint red = 0;
    guint green = 0;
    guint blue = 0;
    gchar component[3] = {0};
    gchar alpha_buf[G_ASCII_DTOSTR_BUF_SIZE] = {0};
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
    g_ascii_formatd(alpha_buf, sizeof(alpha_buf), "%.2f", clamped);
    return g_strdup_printf("rgba(%u,%u,%u,%s)", red, green, blue, alpha_buf);
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

static gchar *notification_rules_file_path(void) {
    return g_build_filename(g_get_home_dir(), ".local", "state", "hanauta", "notification-rules.ini", NULL);
}

static gchar *settings_file_path(void) {
    return g_build_filename(g_get_home_dir(), ".local", "state", "hanauta", "notification-center", "settings.json", NULL);
}

static gchar *control_file_path(void) {
    gchar *dir = state_dir_path();
    gchar *path = g_build_filename(dir, "control.json", NULL);
    g_free(dir);
    return path;
}

static gchar *toast_override_file_path(void) {
    gchar *dir = state_dir_path();
    gchar *path = g_build_filename(dir, "toast.css", NULL);
    g_free(dir);
    return path;
}

static gchar *toast_default_file_path(void) {
    return g_build_filename(g_get_home_dir(), ".config", "i3", "hanauta", "src", "service", "hanauta-notifyd.css", NULL);
}

static gchar *app_aliases_file_path(void) {
    gchar *dir = state_dir_path();
    gchar *path = g_build_filename(dir, "app-aliases.toon", NULL);
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
    g_free(entry->action);
    g_free(entry->label);
    g_free(entry->url);
    g_free(entry->method);
    g_free(entry->body);
    g_free(entry->value);
    g_free(entry);
}

static void payload_free(NotificationPayload *payload) {
    if (payload == NULL) {
        return;
    }
    g_free(payload->app_name);
    g_free(payload->app_icon);
    g_free(payload->desktop_entry);
    g_free(payload->image_path);
    if (payload->image_pixbuf != NULL) {
        g_object_unref(payload->image_pixbuf);
    }
    g_free(payload->summary);
    g_free(payload->body);
    if (payload->actions != NULL) {
        g_ptr_array_free(payload->actions, TRUE);
    }
    g_free(payload);
}

static void pixbuf_pixels_destroy(guchar *pixels, gpointer data) {
    (void)data;
    g_free(pixels);
}

static GdkPixbuf *pixbuf_from_image_data_variant(GVariant *variant) {
    gint32 width = 0;
    gint32 height = 0;
    gint32 rowstride = 0;
    gboolean has_alpha = FALSE;
    gint32 bits_per_sample = 0;
    gint32 channels = 0;
    GVariant *bytes_variant = NULL;
    gconstpointer raw = NULL;
    gsize data_len = 0;
    guchar *pixels = NULL;
    GdkPixbuf *pixbuf = NULL;

    if (variant == NULL || !g_variant_is_of_type(variant, G_VARIANT_TYPE("(iiibiiay)"))) {
        return NULL;
    }

    g_variant_get(
        variant,
        "(iiibii@ay)",
        &width,
        &height,
        &rowstride,
        &has_alpha,
        &bits_per_sample,
        &channels,
        &bytes_variant
    );
    if (bytes_variant == NULL) {
        return NULL;
    }
    raw = g_variant_get_fixed_array(bytes_variant, &data_len, sizeof(guchar));
    if (raw == NULL || data_len == 0 || width <= 0 || height <= 0 || rowstride <= 0) {
        g_variant_unref(bytes_variant);
        return NULL;
    }
    if (!(channels == 3 || channels == 4)) {
        g_variant_unref(bytes_variant);
        return NULL;
    }
    if (bits_per_sample != 8) {
        g_variant_unref(bytes_variant);
        return NULL;
    }
    pixels = g_memdup2(raw, data_len);
    pixbuf = gdk_pixbuf_new_from_data(
        pixels,
        GDK_COLORSPACE_RGB,
        has_alpha,
        bits_per_sample,
        width,
        height,
        rowstride,
        pixbuf_pixels_destroy,
        NULL
    );
    if (pixbuf == NULL) {
        g_free(pixels);
    }
    g_variant_unref(bytes_variant);
    return pixbuf;
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

static gchar *replace_all(const gchar *source, const gchar *needle, const gchar *replacement) {
    GString *result = NULL;
    const gchar *cursor = source;
    gsize needle_len = strlen(needle);
    gsize replacement_len = strlen(replacement);
    const gchar *match = NULL;

    if (source == NULL || needle == NULL || replacement == NULL || needle_len == 0) {
        return g_strdup(source != NULL ? source : "");
    }

    result = g_string_new("");
    while ((match = g_strstr_len(cursor, -1, needle)) != NULL) {
        g_string_append_len(result, cursor, (gssize)(match - cursor));
        g_string_append_len(result, replacement, (gssize)replacement_len);
        cursor = match + needle_len;
    }
    g_string_append(result, cursor);
    return g_string_free(result, FALSE);
}

static void apply_emoji_fallback_to_label(GtkWidget *widget) {
    PangoAttrList *attrs = NULL;
    if (widget == NULL || !GTK_IS_LABEL(widget)) {
        return;
    }
    attrs = pango_attr_list_new();
    pango_attr_list_insert(attrs, pango_attr_fallback_new(TRUE));
    gtk_label_set_attributes(GTK_LABEL(widget), attrs);
    pango_attr_list_unref(attrs);
}

static gboolean is_emoji_codepoint(gunichar ch) {
    return
        (ch >= 0x1F300 && ch <= 0x1FAFF) ||
        (ch >= 0x2600 && ch <= 0x27BF) ||
        (ch >= 0xFE00 && ch <= 0xFE0F) ||
        (ch >= 0x1F1E6 && ch <= 0x1F1FF) ||
        (ch >= 0x1F3FB && ch <= 0x1F3FF) ||
        ch == 0x200D ||
        ch == 0x20E3;
}

static gchar *markup_with_emoji_font(const gchar *text) {
    const gchar *cursor = text != NULL ? text : "";
    GString *markup = NULL;
    gboolean in_emoji_span = FALSE;
    gboolean has_emoji = FALSE;

    while (*cursor != '\0') {
        gunichar ch = g_utf8_get_char(cursor);
        gunichar next = 0;
        gchar buf[8] = {0};
        gchar *escaped = NULL;
        gboolean emoji = is_emoji_codepoint(ch);

        if (!emoji && *cursor != '\0') {
            const gchar *next_ptr = g_utf8_next_char(cursor);
            if (*next_ptr != '\0') {
                next = g_utf8_get_char(next_ptr);
                if ((ch == '#' || ch == '*' || (ch >= '0' && ch <= '9')) && (next == 0xFE0F || next == 0x20E3)) {
                    emoji = TRUE;
                }
            }
        }

        if (markup == NULL) {
            markup = g_string_new("");
        }
        if (emoji && !in_emoji_span) {
            g_string_append(markup, "<span font_desc=\"Noto Color Emoji\">");
            in_emoji_span = TRUE;
            has_emoji = TRUE;
        } else if (!emoji && in_emoji_span) {
            g_string_append(markup, "</span>");
            in_emoji_span = FALSE;
        }

        gint len = g_unichar_to_utf8(ch, buf);
        buf[len] = '\0';
        escaped = g_markup_escape_text(buf, -1);
        g_string_append(markup, escaped);
        g_free(escaped);
        cursor = g_utf8_next_char(cursor);
    }

    if (!has_emoji) {
        if (markup != NULL) {
            g_string_free(markup, TRUE);
        }
        return NULL;
    }
    if (in_emoji_span) {
        g_string_append(markup, "</span>");
    }
    return g_string_free(markup, FALSE);
}

static void apply_text_with_emoji_markup(GtkWidget *widget, const gchar *text) {
    gchar *markup = NULL;
    if (widget == NULL || !GTK_IS_LABEL(widget)) {
        return;
    }
    markup = markup_with_emoji_font(text);
    if (markup != NULL) {
        gtk_label_set_markup(GTK_LABEL(widget), markup);
        g_free(markup);
    } else {
        gtk_label_set_text(GTK_LABEL(widget), text != NULL ? text : "");
    }
}

static gchar *load_toast_css(const ThemePalette *theme) {
    static const gchar *fallback_template =
        "#hanauta-toast-window { background: transparent; }\n"
        "#card { background: {{CARD_BG}}; border: 1px solid {{CARD_BORDER}}; border-radius: 18px; box-shadow: 0 0 16px {{CARD_SHADOW}}; }\n"
        "#content { padding: 10px; }\n"
        "#toastIcon { padding: 0; }\n"
        "#appLabel { color: {{APP_LABEL}}; font-weight: 800; letter-spacing: 0.4px; }\n"
        "#summaryLabel { color: {{SUMMARY_COLOR}}; font-weight: 800; font-size: 13px; }\n"
        "#bodyLabel { color: {{BODY_COLOR}}; font-size: 12px; }\n"
        "#closeButton { background: {{CLOSE_BG}}; color: {{CLOSE_FG}}; border-radius: 10px; padding: 1px 6px; border: none; }\n"
        "#actionButton { background: {{ACTION_BG}}; color: {{ACTION_FG}}; border-radius: 12px; padding: 5px 10px; border: none; font-weight: 800; }\n"
        "#actionButton:hover { background: {{ACTION_HOVER}}; color: {{ACTION_HOVER_FG}}; }\n";
    gchar *override_path = toast_override_file_path();
    gchar *default_path = toast_default_file_path();
    gchar *template = NULL;
    gchar *card_bg = hex_to_rgba(theme->surface_container, 0.94);
    gchar *card_border = hex_to_rgba(theme->outline, 0.18);
    gchar *card_shadow = hex_to_rgba(theme->primary, 0.24);
    gchar *app_label = g_strdup(theme->primary);
    gchar *summary_color = g_strdup(theme->on_surface);
    gchar *body_color = hex_to_rgba(theme->on_surface_variant, 0.78);
    gchar *close_bg = hex_to_rgba(theme->on_surface, 0.08);
    gchar *close_fg = g_strdup(theme->on_surface);
    gchar *action_bg = g_strdup(theme->primary);
    gchar *action_fg = g_strdup(theme->on_primary);
    gchar *action_hover = g_strdup(theme->primary_container);
    gchar *action_hover_fg = g_strdup(theme->on_primary_container);
    gchar *css = NULL;
    gchar *next = NULL;

    if (!g_file_get_contents(override_path, &template, NULL, NULL) || template == NULL) {
        g_clear_pointer(&template, g_free);
        if (!g_file_get_contents(default_path, &template, NULL, NULL) || template == NULL) {
            g_clear_pointer(&template, g_free);
            template = g_strdup(fallback_template);
        }
    }

    css = replace_all(template, "{{CARD_BG}}", card_bg);
    next = replace_all(css, "{{CARD_BORDER}}", card_border);
    g_free(css);
    css = next;
    next = replace_all(css, "{{CARD_SHADOW}}", card_shadow);
    g_free(css);
    css = next;
    next = replace_all(css, "{{APP_LABEL}}", app_label);
    g_free(css);
    css = next;
    next = replace_all(css, "{{SUMMARY_COLOR}}", summary_color);
    g_free(css);
    css = next;
    next = replace_all(css, "{{BODY_COLOR}}", body_color);
    g_free(css);
    css = next;
    next = replace_all(css, "{{CLOSE_BG}}", close_bg);
    g_free(css);
    css = next;
    next = replace_all(css, "{{CLOSE_FG}}", close_fg);
    g_free(css);
    css = next;
    next = replace_all(css, "{{ACTION_BG}}", action_bg);
    g_free(css);
    css = next;
    next = replace_all(css, "{{ACTION_FG}}", action_fg);
    g_free(css);
    css = next;
    next = replace_all(css, "{{ACTION_HOVER}}", action_hover);
    g_free(css);
    css = next;
    next = replace_all(css, "{{ACTION_HOVER_FG}}", action_hover_fg);
    g_free(css);
    css = next;

    g_free(template);
    g_free(override_path);
    g_free(default_path);
    g_free(card_bg);
    g_free(card_border);
    g_free(card_shadow);
    g_free(app_label);
    g_free(summary_color);
    g_free(body_color);
    g_free(close_bg);
    g_free(close_fg);
    g_free(action_bg);
    g_free(action_fg);
    g_free(action_hover);
    g_free(action_hover_fg);
    return css;
}

static gboolean str_contains_casefold(const gchar *haystack, const gchar *needle) {
    gboolean matched = FALSE;
    gchar *haystack_folded = NULL;
    gchar *needle_folded = NULL;
    if (haystack == NULL || needle == NULL || *needle == '\0') {
        return FALSE;
    }
    haystack_folded = g_utf8_casefold(haystack, -1);
    needle_folded = g_utf8_casefold(needle, -1);
    matched = g_strstr_len(haystack_folded, -1, needle_folded) != NULL;
    g_free(haystack_folded);
    g_free(needle_folded);
    return matched;
}

static gboolean csv_text_matches(const gchar *text, const gchar *csv) {
    gboolean matched = FALSE;
    gchar **parts = NULL;
    if (csv == NULL || *csv == '\0') {
        return FALSE;
    }
    parts = g_strsplit(csv, ",", -1);
    for (guint i = 0; parts[i] != NULL; ++i) {
        gchar *trimmed = g_strstrip(parts[i]);
        if (*trimmed == '\0') {
            continue;
        }
        if (str_contains_casefold(text, trimmed)) {
            matched = TRUE;
            break;
        }
    }
    g_strfreev(parts);
    return matched;
}

static gboolean csv_exact_ci_match(const gchar *text, const gchar *csv) {
    gchar **parts = NULL;
    gboolean matched = FALSE;
    if (text == NULL || *text == '\0' || csv == NULL || *csv == '\0') {
        return FALSE;
    }
    parts = g_strsplit(csv, ",", -1);
    for (guint i = 0; parts[i] != NULL; ++i) {
        gchar *trimmed = g_strstrip(parts[i]);
        if (*trimmed == '\0') {
            continue;
        }
        if (g_ascii_strcasecmp(trimmed, text) == 0) {
            matched = TRUE;
            break;
        }
    }
    g_strfreev(parts);
    return matched;
}

static void ensure_app_aliases_file(void) {
    gchar *path = app_aliases_file_path();
    static const gchar *template_text =
        "# Hanauta notification aliases (.toon)\n"
        "#\n"
        "# Each section maps noisy app IDs into friendly titles/icons.\n"
        "#\n"
        "# Match keys (comma-separated):\n"
        "#   app_names        = raw DBus app_name values\n"
        "#   desktop_entries  = desktop-entry hint values\n"
        "#   contains         = case-insensitive substrings against app_name\n"
        "#\n"
        "# Output keys:\n"
        "#   title = display title for toast/history\n"
        "#   icon  = icon name OR absolute path (.png/.svg/.gif/.webp)\n"
        "#          Animated images are supported when the decoder supports it.\n"
        "#\n"
        "[youtube_music]\n"
        "app_names = com.github.th_ch.youtube_music\n"
        "desktop_entries = youtube-music\n"
        "contains = youtube_music,youtube-music\n"
        "title = YouTube Music\n"
        "# icon = /home/you/.local/share/icons/youtube-music.gif\n";
    if (!g_file_test(path, G_FILE_TEST_EXISTS)) {
        ensure_state_dir();
        g_file_set_contents(path, template_text, -1, NULL);
    }
    g_free(path);
}

static void apply_app_aliases(NotificationPayload *payload) {
    gchar *path = NULL;
    GKeyFile *key_file = NULL;
    gsize group_count = 0;
    gchar **groups = NULL;
    if (payload == NULL) {
        return;
    }
    ensure_app_aliases_file();
    path = app_aliases_file_path();
    key_file = g_key_file_new();
    if (!g_key_file_load_from_file(key_file, path, G_KEY_FILE_NONE, NULL)) {
        g_key_file_free(key_file);
        g_free(path);
        return;
    }

    groups = g_key_file_get_groups(key_file, &group_count);
    for (gsize i = 0; i < group_count; ++i) {
        const gchar *group = groups[i];
        gchar *app_names = g_key_file_get_string(key_file, group, "app_names", NULL);
        gchar *desktop_entries = g_key_file_get_string(key_file, group, "desktop_entries", NULL);
        gchar *contains = g_key_file_get_string(key_file, group, "contains", NULL);
        gchar *title = g_key_file_get_string(key_file, group, "title", NULL);
        gchar *icon = g_key_file_get_string(key_file, group, "icon", NULL);
        gboolean matched = FALSE;

        if (app_names != NULL && *app_names != '\0' && csv_exact_ci_match(payload->app_name, app_names)) {
            matched = TRUE;
        }
        if (!matched && desktop_entries != NULL && *desktop_entries != '\0' &&
            csv_exact_ci_match(payload->desktop_entry, desktop_entries)) {
            matched = TRUE;
        }
        if (!matched && contains != NULL && *contains != '\0' &&
            csv_text_matches(payload->app_name, contains)) {
            matched = TRUE;
        }

        if (matched) {
            if (title != NULL && *title != '\0') {
                g_free(payload->app_name);
                payload->app_name = g_strdup(title);
            }
            if (icon != NULL && *icon != '\0') {
                g_free(payload->app_icon);
                payload->app_icon = g_strdup(icon);
            }
            g_free(app_names);
            g_free(desktop_entries);
            g_free(contains);
            g_free(title);
            g_free(icon);
            break;
        }
        g_free(app_names);
        g_free(desktop_entries);
        g_free(contains);
        g_free(title);
        g_free(icon);
    }
    g_strfreev(groups);
    g_key_file_free(key_file);
    g_free(path);
}

static gboolean process_list_match(const gchar *csv) {
    gchar **parts = NULL;
    gboolean matched = FALSE;
    if (csv == NULL || *csv == '\0') {
        return FALSE;
    }
    parts = g_strsplit(csv, ",", -1);
    for (guint i = 0; parts[i] != NULL; ++i) {
        gchar *trimmed = g_strstrip(parts[i]);
        gchar *stdout_data = NULL;
        gchar *stderr_data = NULL;
        gint exit_status = 1;
        const gchar *argv[] = {"pgrep", "-af", trimmed, NULL};
        if (*trimmed == '\0') {
            continue;
        }
        if (g_spawn_sync(NULL, (gchar **)argv, NULL, G_SPAWN_SEARCH_PATH, NULL, NULL, &stdout_data, &stderr_data, &exit_status, NULL)) {
            if (exit_status == 0 && stdout_data != NULL && *stdout_data != '\0') {
                matched = TRUE;
            }
        }
        g_free(stdout_data);
        g_free(stderr_data);
        if (matched) {
            break;
        }
    }
    g_strfreev(parts);
    return matched;
}

static gboolean should_ignore_notification(const NotificationPayload *payload) {
    gboolean ignored = FALSE;
    gchar *path = notification_rules_file_path();
    GKeyFile *key_file = g_key_file_new();
    gsize group_count = 0;
    gchar **groups = NULL;

    if (!g_key_file_load_from_file(key_file, path, G_KEY_FILE_NONE, NULL)) {
        g_key_file_free(key_file);
        g_free(path);
        return FALSE;
    }

    groups = g_key_file_get_groups(key_file, &group_count);
    for (gsize i = 0; i < group_count; ++i) {
        const gchar *group = groups[i];
        gchar *source_app = NULL;
        gchar *summary_contains = NULL;
        gchar *body_contains = NULL;
        gchar *processes = NULL;
        gchar *action = NULL;
        gboolean enabled = FALSE;
        gboolean summary_match = FALSE;
        gboolean body_match = FALSE;
        gboolean has_content_matcher = FALSE;

        if (!g_str_has_prefix(group, "rule.")) {
            continue;
        }
        enabled = g_key_file_get_boolean(key_file, group, "enabled", NULL);
        if (!enabled) {
            continue;
        }

        action = g_key_file_get_string(key_file, group, "action", NULL);
        if (action == NULL || g_ascii_strcasecmp(action, "ignore") != 0) {
            g_free(action);
            continue;
        }

        source_app = g_key_file_get_string(key_file, group, "source_app", NULL);
        if (source_app != NULL && *source_app != '\0' && g_strcmp0(source_app, payload->app_name) != 0) {
            g_free(source_app);
            g_free(action);
            continue;
        }

        summary_contains = g_key_file_get_string(key_file, group, "summary_contains", NULL);
        body_contains = g_key_file_get_string(key_file, group, "body_contains", NULL);
        if (summary_contains != NULL && *summary_contains != '\0') {
            has_content_matcher = TRUE;
            summary_match = csv_text_matches(payload->summary, summary_contains);
        }
        if (body_contains != NULL && *body_contains != '\0') {
            has_content_matcher = TRUE;
            body_match = csv_text_matches(payload->body, body_contains);
        }
        if (has_content_matcher && !summary_match && !body_match) {
            g_free(source_app);
            g_free(summary_contains);
            g_free(body_contains);
            g_free(action);
            continue;
        }

        processes = g_key_file_get_string(key_file, group, "processes", NULL);
        if (processes != NULL && *processes != '\0' && !process_list_match(processes)) {
            g_free(source_app);
            g_free(summary_contains);
            g_free(body_contains);
            g_free(processes);
            g_free(action);
            continue;
        }

        ignored = TRUE;
        g_free(source_app);
        g_free(summary_contains);
        g_free(body_contains);
        g_free(processes);
        g_free(action);
        break;
    }

    g_strfreev(groups);
    g_key_file_free(key_file);
    g_free(path);
    return ignored;
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

static gboolean execute_action_entry(const ActionEntry *entry) {
    if (entry == NULL || entry->action == NULL || *entry->action == '\0') {
        return FALSE;
    }
    if (g_strcmp0(entry->action, "view") == 0) {
        if (entry->url != NULL && *entry->url != '\0') {
            const gchar *argv[] = {"xdg-open", entry->url, NULL};
            g_spawn_async(NULL, (gchar **)argv, NULL, G_SPAWN_SEARCH_PATH, NULL, NULL, NULL, NULL);
            return TRUE;
        }
        return FALSE;
    }
    if (g_strcmp0(entry->action, "http") == 0) {
        if (entry->url != NULL && *entry->url != '\0') {
            const gchar *method = (entry->method != NULL && *entry->method != '\0') ? entry->method : "POST";
            const gchar *argv_with_body[] = {"curl", "-fsSL", "-X", method, "-d", entry->body, entry->url, NULL};
            const gchar *argv_without_body[] = {"curl", "-fsSL", "-X", method, entry->url, NULL};
            g_spawn_async(
                NULL,
                (gchar **)((entry->body != NULL && *entry->body != '\0') ? argv_with_body : argv_without_body),
                NULL,
                G_SPAWN_SEARCH_PATH | G_SPAWN_STDOUT_TO_DEV_NULL | G_SPAWN_STDERR_TO_DEV_NULL,
                NULL,
                NULL,
                NULL,
                NULL
            );
            return TRUE;
        }
        return FALSE;
    }
    if (g_strcmp0(entry->action, "copy") == 0) {
        const gchar *value = entry->value != NULL ? entry->value : "";
        GtkClipboard *clipboard = gtk_clipboard_get(GDK_SELECTION_CLIPBOARD);
        GtkClipboard *primary = gtk_clipboard_get(GDK_SELECTION_PRIMARY);
        gtk_clipboard_set_text(clipboard, value, -1);
        gtk_clipboard_store(clipboard);
        gtk_clipboard_set_text(primary, value, -1);
        return TRUE;
    }
    return FALSE;
}

static gboolean str_eq_ci(const gchar *left, const gchar *right) {
    if (left == NULL || right == NULL) {
        return FALSE;
    }
    return g_ascii_strcasecmp(left, right) == 0;
}

static gboolean action_looks_like_view(const gchar *key, const gchar *label) {
    if (str_eq_ci(key, "default") || str_eq_ci(key, "view") || str_eq_ci(key, "open")) {
        return TRUE;
    }
    if (label == NULL || *label == '\0') {
        return FALSE;
    }
    return str_eq_ci(label, "view") || str_eq_ci(label, "open") || str_eq_ci(label, "show");
}

static gboolean i3_focus_criteria(const gchar *criteria) {
    const gchar *argv[] = {"i3-msg", criteria, NULL};
    gchar *stdout_data = NULL;
    gchar *stderr_data = NULL;
    gint exit_status = 1;
    gboolean focused = FALSE;
    if (criteria == NULL || *criteria == '\0') {
        return FALSE;
    }
    if (g_spawn_sync(
            NULL,
            (gchar **)argv,
            NULL,
            G_SPAWN_SEARCH_PATH,
            NULL,
            NULL,
            &stdout_data,
            &stderr_data,
            &exit_status,
            NULL
        )) {
        if (exit_status == 0 && stdout_data != NULL && g_strstr_len(stdout_data, -1, "\"success\":true") != NULL) {
            focused = TRUE;
        }
    }
    g_free(stdout_data);
    g_free(stderr_data);
    return focused;
}

static gchar *criteria_fragment_from_text(const gchar *text) {
    GString *fragment = NULL;
    const gchar *cursor = NULL;
    if (text == NULL || *text == '\0') {
        return g_strdup("");
    }
    fragment = g_string_new("");
    for (cursor = text; *cursor != '\0'; ++cursor) {
        gchar ch = *cursor;
        if ((ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || (ch >= '0' && ch <= '9')) {
            g_string_append_c(fragment, ch);
        } else if (ch == ' ' || ch == '-' || ch == '_' || ch == '.') {
            g_string_append(fragment, ".*");
        }
    }
    if (fragment->len == 0) {
        g_string_assign(fragment, ".*");
    }
    return g_string_free(fragment, FALSE);
}

static gboolean activate_notification_source(guint sender_pid, const gchar *desktop_entry, const gchar *app_name) {
    gboolean launched = FALSE;
    if (sender_pid > 0) {
        gchar *criteria = g_strdup_printf("[pid=\"%u\"] focus", sender_pid);
        launched = i3_focus_criteria(criteria);
        g_free(criteria);
    }
    if (!launched && desktop_entry != NULL && *desktop_entry != '\0') {
        gchar *base = g_strdup(desktop_entry);
        gchar *fragment = NULL;
        if (g_str_has_suffix(base, ".desktop")) {
            base[strlen(base) - strlen(".desktop")] = '\0';
        }
        fragment = criteria_fragment_from_text(base);
        if (fragment != NULL && *fragment != '\0') {
            gchar *class_criteria = g_strdup_printf("[class=\"(?i)%s\"] focus", fragment);
            gchar *instance_criteria = g_strdup_printf("[instance=\"(?i)%s\"] focus", fragment);
            launched = i3_focus_criteria(class_criteria);
            if (!launched) {
                launched = i3_focus_criteria(instance_criteria);
            }
            g_free(class_criteria);
            g_free(instance_criteria);
        }
        g_free(fragment);
        g_free(base);
    }
    if (!launched && app_name != NULL && *app_name != '\0') {
        gchar *fragment = criteria_fragment_from_text(app_name);
        if (fragment != NULL && *fragment != '\0') {
            gchar *title_criteria = g_strdup_printf("[title=\"(?i)%s\"] focus", fragment);
            launched = i3_focus_criteria(title_criteria);
            g_free(title_criteria);
        }
        g_free(fragment);
    }
    if (!launched && desktop_entry != NULL && *desktop_entry != '\0') {
        gchar *desktop_id = g_strdup(desktop_entry);
        if (g_str_has_suffix(desktop_id, ".desktop")) {
            desktop_id[strlen(desktop_id) - strlen(".desktop")] = '\0';
        }
        const gchar *argv_launch[] = {"gtk-launch", desktop_id, NULL};
        launched = g_spawn_async(
            NULL,
            (gchar **)argv_launch,
            NULL,
            G_SPAWN_SEARCH_PATH | G_SPAWN_STDOUT_TO_DEV_NULL | G_SPAWN_STDERR_TO_DEV_NULL,
            NULL,
            NULL,
            NULL,
            NULL
        );
        g_free(desktop_id);
    }
    if (!launched && app_name != NULL && *app_name != '\0') {
        const gchar *argv_open[] = {"xdg-open", app_name, NULL};
        launched = g_spawn_async(
            NULL,
            (gchar **)argv_open,
            NULL,
            G_SPAWN_SEARCH_PATH | G_SPAWN_STDOUT_TO_DEV_NULL | G_SPAWN_STDERR_TO_DEV_NULL,
            NULL,
            NULL,
            NULL,
            NULL
        );
    }
    return launched;
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
        gint toast_width = 320;
        gint toast_height = 120;
        gtk_widget_show_all(toast->window);
        gtk_window_get_size(GTK_WINDOW(toast->window), &toast_width, &toast_height);
        gtk_window_move(GTK_WINDOW(toast->window), geometry.x + geometry.width - toast_width - 24, geometry.y + y);
        y += toast_height + 8;
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
    const gchar *action_label = gtk_button_get_label(button);
    const gchar *desktop_entry = g_object_get_data(G_OBJECT(button), "action-desktop-entry");
    const gchar *app_name = g_object_get_data(G_OBJECT(button), "action-app-name");
    guint sender_pid = GPOINTER_TO_UINT(g_object_get_data(G_OBJECT(button), "action-sender-pid"));
    ActionEntry entry = {0};
    entry.key = (gchar *)action_key;
    entry.action = g_object_get_data(G_OBJECT(button), "action-type");
    entry.url = g_object_get_data(G_OBJECT(button), "action-url");
    entry.method = g_object_get_data(G_OBJECT(button), "action-method");
    entry.body = g_object_get_data(G_OBJECT(button), "action-body");
    entry.value = g_object_get_data(G_OBJECT(button), "action-value");
    entry.clear = GPOINTER_TO_INT(g_object_get_data(G_OBJECT(button), "action-clear")) != 0;
    gboolean executed = execute_action_entry(&entry);
    if (!executed && action_looks_like_view(action_key, action_label)) {
        activate_notification_source(sender_pid, desktop_entry, app_name);
    }
    emit_action(id, action_key);
    if (entry.clear) {
        dismiss_toast(id, 2);
    }
}

static GtkWidget *make_label(const gchar *name, const gchar *text, gdouble xalign) {
    GtkWidget *label = gtk_label_new(text != NULL ? text : "");
    gtk_widget_set_name(label, name);
    gtk_label_set_xalign(GTK_LABEL(label), (gfloat)xalign);
    gtk_label_set_line_wrap(GTK_LABEL(label), TRUE);
    gtk_label_set_line_wrap_mode(GTK_LABEL(label), PANGO_WRAP_WORD_CHAR);
    apply_emoji_fallback_to_label(label);
    apply_text_with_emoji_markup(label, text);
    return label;
}

static gboolean notification_is_weather(const NotificationPayload *payload) {
    if (payload == NULL) {
        return FALSE;
    }
    if (str_contains_casefold(payload->app_name, "weather")) {
        return TRUE;
    }
    if (str_contains_casefold(payload->summary, "weather")) {
        return TRUE;
    }
    if (str_contains_casefold(payload->summary, "sunrise") || str_contains_casefold(payload->summary, "sunset")) {
        return TRUE;
    }
    if (str_contains_casefold(payload->body, "sunrise") || str_contains_casefold(payload->body, "sunset")) {
        return TRUE;
    }
    if (str_contains_casefold(payload->app_icon, "weather")
        || str_contains_casefold(payload->app_icon, "sunrise")
        || str_contains_casefold(payload->app_icon, "sunset")
        || str_contains_casefold(payload->app_icon, "clear-day")
        || str_contains_casefold(payload->app_icon, "clear-night")
        || str_contains_casefold(payload->app_icon, "overcast")
        || str_contains_casefold(payload->app_icon, "thunderstorms")
        || str_contains_casefold(payload->app_icon, "fog")) {
        return TRUE;
    }
    return FALSE;
}

static gchar *resolve_weather_icon_alias_name(const gchar *icon_name) {
    gchar *base = NULL;
    if (icon_name == NULL || *icon_name == '\0') {
        return NULL;
    }
    base = g_ascii_strdown(icon_name, -1);
    if (g_str_has_suffix(base, "-symbolic")) {
        base[strlen(base) - strlen("-symbolic")] = '\0';
    }
    if (g_strcmp0(base, "weather-clear") == 0) {
        g_free(base);
        return g_strdup("clear-day");
    }
    if (g_strcmp0(base, "weather-clear-night") == 0) {
        g_free(base);
        return g_strdup("clear-night");
    }
    if (g_strcmp0(base, "weather-few-clouds") == 0 || g_strcmp0(base, "weather-partly-cloudy") == 0) {
        g_free(base);
        return g_strdup("partly-cloudy-day");
    }
    if (g_strcmp0(base, "weather-overcast") == 0) {
        g_free(base);
        return g_strdup("overcast");
    }
    if (g_strcmp0(base, "weather-showers") == 0 || g_strcmp0(base, "weather-showers-scattered") == 0) {
        g_free(base);
        return g_strdup("overcast-rain");
    }
    if (g_strcmp0(base, "weather-storm") == 0 || g_strcmp0(base, "weather-severe-alert") == 0) {
        g_free(base);
        return g_strdup("thunderstorms");
    }
    if (g_strcmp0(base, "weather-snow") == 0) {
        g_free(base);
        return g_strdup("overcast-snow");
    }
    if (g_strcmp0(base, "weather-fog") == 0 || g_strcmp0(base, "weather-mist") == 0) {
        g_free(base);
        return g_strdup("fog");
    }
    if (g_strcmp0(base, "daytime-sunrise") == 0) {
        g_free(base);
        return g_strdup("sunrise");
    }
    if (g_strcmp0(base, "daytime-sunset") == 0) {
        g_free(base);
        return g_strdup("sunset");
    }
    return base;
}

static gchar *resolve_bundled_weather_icon_path(const gchar *icon_name) {
    gchar *base_name = resolve_weather_icon_alias_name(icon_name);
    gchar *path = NULL;
    if (base_name == NULL || *base_name == '\0') {
        g_free(base_name);
        return NULL;
    }
    path = g_build_filename(
        g_get_home_dir(),
        ".config",
        "i3",
        "hanauta",
        "src",
        "assets",
        "weather-icons",
        "monochrome",
        "svg-static",
        NULL
    );
    gchar *candidate = g_strdup_printf("%s/%s.svg", path, base_name);
    if (g_file_test(candidate, G_FILE_TEST_EXISTS)) {
        g_free(path);
        g_free(base_name);
        return candidate;
    }
    g_free(candidate);
    candidate = g_build_filename(
        g_get_home_dir(),
        ".config",
        "i3",
        "hanauta",
        "src",
        "assets",
        "weather-icons",
        "fill",
        "svg",
        NULL
    );
    path = g_strdup_printf("%s/%s.svg", candidate, base_name);
    g_free(candidate);
    if (g_file_test(path, G_FILE_TEST_EXISTS)) {
        g_free(base_name);
        return path;
    }
    g_free(path);
    g_free(base_name);
    return NULL;
}

static GtkWidget *make_notification_icon(const gchar *icon_name, GdkPixbuf *image_pixbuf, gint target_size) {
    if (image_pixbuf != NULL) {
        gint width = gdk_pixbuf_get_width(image_pixbuf);
        gint height = gdk_pixbuf_get_height(image_pixbuf);
        gint target = MAX(16, target_size);
        GdkPixbuf *scaled = NULL;
        GtkWidget *image = NULL;
        if (width > 0 && height > 0) {
            if (width > height) {
                scaled = gdk_pixbuf_scale_simple(
                    image_pixbuf,
                    target,
                    MAX(1, (height * target) / width),
                    GDK_INTERP_BILINEAR
                );
            } else {
                scaled = gdk_pixbuf_scale_simple(
                    image_pixbuf,
                    MAX(1, (width * target) / height),
                    target,
                    GDK_INTERP_BILINEAR
                );
            }
        }
        image = gtk_image_new_from_pixbuf(scaled != NULL ? scaled : image_pixbuf);
        if (scaled != NULL) {
            g_object_unref(scaled);
        }
        gtk_widget_set_name(image, "toastIcon");
        gtk_widget_set_size_request(image, target, target);
        return image;
    }
    if (icon_name == NULL || *icon_name == '\0') {
        return NULL;
    }
    GtkWidget *image = NULL;
    gchar *resolved_path = NULL;
    if (g_str_has_prefix(icon_name, "file://")) {
        resolved_path = g_filename_from_uri(icon_name, NULL, NULL);
    }
    gchar *bundled_weather_icon = NULL;
    const gchar *effective_icon = (resolved_path != NULL && *resolved_path != '\0') ? resolved_path : icon_name;
    if (!g_file_test(effective_icon, G_FILE_TEST_EXISTS)) {
        bundled_weather_icon = resolve_bundled_weather_icon_path(effective_icon);
        if (bundled_weather_icon != NULL && *bundled_weather_icon != '\0') {
            effective_icon = bundled_weather_icon;
        }
    }
    if (g_file_test(effective_icon, G_FILE_TEST_EXISTS)) {
        GError *error = NULL;
        gint target = MAX(16, target_size);
        GdkPixbuf *scaled = gdk_pixbuf_new_from_file_at_scale(
            effective_icon,
            target,
            target,
            TRUE,
            &error
        );
        if (scaled != NULL) {
            image = gtk_image_new_from_pixbuf(scaled);
            g_object_unref(scaled);
        } else {
            g_clear_error(&error);
            image = gtk_image_new_from_file(effective_icon);
        }
    } else {
        image = gtk_image_new_from_icon_name(effective_icon, GTK_ICON_SIZE_DIALOG);
        gtk_image_set_pixel_size(GTK_IMAGE(image), MAX(16, target_size));
    }
    g_free(bundled_weather_icon);
    g_free(resolved_path);
    if (image == NULL) {
        return NULL;
    }
    gtk_widget_set_name(image, "toastIcon");
    gtk_widget_set_size_request(image, MAX(16, target_size), MAX(16, target_size));
    return image;
}

static gboolean clear_transparent_window(GtkWidget *widget, cairo_t *cr, gpointer user_data) {
    (void)widget;
    (void)user_data;
    cairo_set_operator(cr, CAIRO_OPERATOR_SOURCE);
    cairo_set_source_rgba(cr, 0.0, 0.0, 0.0, 0.0);
    cairo_paint(cr);
    cairo_set_operator(cr, CAIRO_OPERATOR_OVER);
    return FALSE;
}

static void show_toast(const NotificationPayload *payload) {
    ThemePalette theme;
    gboolean compact_weather = notification_is_weather(payload);
    gint toast_width = compact_weather ? 264 : 320;
    guint outer_padding = compact_weather ? 6 : 10;
    guint content_padding = compact_weather ? 4 : 6;
    gint content_spacing = compact_weather ? 6 : 8;
    gint header_icon_size = compact_weather ? 18 : 22;
    gint art_icon_size = compact_weather ? 42 : 58;
    GtkWidget *window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    GdkScreen *screen = gtk_widget_get_screen(window);
    GdkVisual *visual = screen != NULL ? gdk_screen_get_rgba_visual(screen) : NULL;
    gchar *title = g_strdup_printf("Hanauta Notification %u", payload->id);
    if (visual != NULL && gdk_screen_is_composited(screen)) {
        gtk_widget_set_visual(window, visual);
    }
    gtk_widget_set_app_paintable(window, TRUE);
    g_signal_connect(window, "draw", G_CALLBACK(clear_transparent_window), NULL);
    gtk_window_set_decorated(GTK_WINDOW(window), FALSE);
    gtk_window_set_type_hint(GTK_WINDOW(window), GDK_WINDOW_TYPE_HINT_NOTIFICATION);
    gtk_window_set_role(GTK_WINDOW(window), "notification");
    gtk_window_set_skip_taskbar_hint(GTK_WINDOW(window), TRUE);
    gtk_window_set_skip_pager_hint(GTK_WINDOW(window), TRUE);
    gtk_window_set_keep_above(GTK_WINDOW(window), TRUE);
    gtk_window_stick(GTK_WINDOW(window));
    gtk_window_set_accept_focus(GTK_WINDOW(window), FALSE);
    gtk_window_set_resizable(GTK_WINDOW(window), FALSE);
    gtk_window_set_default_size(GTK_WINDOW(window), toast_width, -1);
    gtk_widget_set_size_request(window, toast_width, -1);
    gtk_window_set_title(GTK_WINDOW(window), title);
    gtk_widget_set_name(window, "hanauta-toast-window");

    GtkWidget *outer = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_container_set_border_width(GTK_CONTAINER(outer), outer_padding);
    gtk_container_add(GTK_CONTAINER(window), outer);

    GtkWidget *card = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_widget_set_name(card, "card");
    gtk_box_pack_start(GTK_BOX(outer), card, TRUE, TRUE, 0);

    GtkWidget *content = gtk_box_new(GTK_ORIENTATION_VERTICAL, content_spacing);
    gtk_widget_set_name(content, "content");
    gtk_container_set_border_width(GTK_CONTAINER(content), content_padding);
    gtk_box_pack_start(GTK_BOX(card), content, TRUE, TRUE, 0);

    GtkWidget *top = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    gtk_box_pack_start(GTK_BOX(content), top, FALSE, FALSE, 0);

    GtkWidget *icon = make_notification_icon(payload->app_icon, NULL, header_icon_size);
    if (icon != NULL) {
        gtk_box_pack_start(GTK_BOX(top), icon, FALSE, FALSE, 0);
    }

    GtkWidget *app_name = make_label("appLabel", payload->app_name[0] != '\0' ? payload->app_name : "Notification", 0.0);
    gtk_label_set_lines(GTK_LABEL(app_name), 1);
    gtk_label_set_ellipsize(GTK_LABEL(app_name), PANGO_ELLIPSIZE_END);
    gtk_label_set_max_width_chars(GTK_LABEL(app_name), compact_weather ? 18 : 26);
    gtk_box_pack_start(GTK_BOX(top), app_name, TRUE, TRUE, 0);

    GtkWidget *close_button = gtk_button_new_with_label("×");
    gtk_widget_set_name(close_button, "closeButton");
    apply_emoji_fallback_to_label(gtk_bin_get_child(GTK_BIN(close_button)));
    g_signal_connect(close_button, "clicked", G_CALLBACK(close_button_clicked), GUINT_TO_POINTER(payload->id));
    gtk_box_pack_end(GTK_BOX(top), close_button, FALSE, FALSE, 0);

    GtkWidget *summary = make_label("summaryLabel", payload->summary, 0.0);
    if (compact_weather) {
        gtk_label_set_max_width_chars(GTK_LABEL(summary), 28);
        gtk_label_set_lines(GTK_LABEL(summary), 2);
        gtk_label_set_ellipsize(GTK_LABEL(summary), PANGO_ELLIPSIZE_END);
    } else {
        gtk_label_set_max_width_chars(GTK_LABEL(summary), 44);
        gtk_label_set_lines(GTK_LABEL(summary), 3);
        gtk_label_set_ellipsize(GTK_LABEL(summary), PANGO_ELLIPSIZE_END);
    }
    gtk_box_pack_start(GTK_BOX(content), summary, FALSE, FALSE, 0);

    if ((payload->image_pixbuf != NULL) || (payload->image_path != NULL && payload->image_path[0] != '\0')) {
        GtkWidget *art_row = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 0);
        GtkWidget *art = make_notification_icon(payload->image_path, payload->image_pixbuf, art_icon_size);
        if (art != NULL) {
            gtk_box_pack_start(GTK_BOX(art_row), art, FALSE, FALSE, 0);
            gtk_box_pack_start(GTK_BOX(content), art_row, FALSE, FALSE, 0);
        } else {
            gtk_widget_destroy(art_row);
        }
    }

    if (payload->body != NULL && payload->body[0] != '\0') {
        GtkWidget *body = make_label("bodyLabel", payload->body, 0.0);
        if (compact_weather) {
            gtk_label_set_max_width_chars(GTK_LABEL(body), 30);
            gtk_label_set_lines(GTK_LABEL(body), 2);
            gtk_label_set_ellipsize(GTK_LABEL(body), PANGO_ELLIPSIZE_END);
        } else {
            gtk_label_set_max_width_chars(GTK_LABEL(body), 46);
            gtk_label_set_lines(GTK_LABEL(body), 4);
            gtk_label_set_ellipsize(GTK_LABEL(body), PANGO_ELLIPSIZE_END);
        }
        gtk_box_pack_start(GTK_BOX(content), body, FALSE, FALSE, 0);
    }

    if (payload->actions != NULL && payload->actions->len > 0) {
        GtkWidget *actions_box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
        gtk_box_pack_start(GTK_BOX(content), actions_box, FALSE, FALSE, 0);
        for (guint i = 0; i < payload->actions->len; ++i) {
            ActionEntry *action = g_ptr_array_index(payload->actions, i);
            GtkWidget *button = gtk_button_new_with_label(action->label != NULL ? action->label : "Action");
            gtk_widget_set_name(button, "actionButton");
            g_object_set_data_full(G_OBJECT(button), "action-key", g_strdup(action->key), g_free);
            g_object_set_data_full(G_OBJECT(button), "action-type", g_strdup(action->action), g_free);
            g_object_set_data_full(G_OBJECT(button), "action-url", g_strdup(action->url), g_free);
            g_object_set_data_full(G_OBJECT(button), "action-method", g_strdup(action->method), g_free);
            g_object_set_data_full(G_OBJECT(button), "action-body", g_strdup(action->body), g_free);
            g_object_set_data_full(G_OBJECT(button), "action-value", g_strdup(action->value), g_free);
            g_object_set_data_full(G_OBJECT(button), "action-desktop-entry", g_strdup(payload->desktop_entry), g_free);
            g_object_set_data_full(G_OBJECT(button), "action-app-name", g_strdup(payload->app_name), g_free);
            g_object_set_data(G_OBJECT(button), "action-sender-pid", GUINT_TO_POINTER(payload->sender_pid));
            g_object_set_data(G_OBJECT(button), "action-clear", GINT_TO_POINTER(action->clear ? 1 : 0));
            apply_emoji_fallback_to_label(gtk_bin_get_child(GTK_BIN(button)));
            apply_text_with_emoji_markup(gtk_bin_get_child(GTK_BIN(button)), action->label != NULL ? action->label : "Action");
            g_signal_connect(button, "clicked", G_CALLBACK(action_button_clicked), GUINT_TO_POINTER(payload->id));
            gtk_box_pack_start(GTK_BOX(actions_box), button, FALSE, FALSE, 0);
        }
    }

    load_theme_palette(&theme);
    GtkCssProvider *provider = gtk_css_provider_new();
    gchar *css = load_toast_css(&theme);
    gtk_css_provider_load_from_data(provider, css, -1, NULL);
    GtkStyleContext *context = gtk_widget_get_style_context(window);
    gtk_style_context_add_provider(context, GTK_STYLE_PROVIDER(provider), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    gtk_style_context_add_provider_for_screen(
        gdk_screen_get_default(),
        GTK_STYLE_PROVIDER(provider),
        GTK_STYLE_PROVIDER_PRIORITY_APPLICATION
    );
    g_object_unref(provider);
    g_free(css);
    g_free(title);

    ToastWindow *toast = g_new0(ToastWindow, 1);
    toast->window = window;
    toast->id = payload->id;
    toast->timeout_id = g_timeout_add(payload->expire_timeout > 0 ? (guint)payload->expire_timeout : 10000, toast_timeout_cb, GUINT_TO_POINTER(payload->id));
    g_hash_table_insert(g_daemon.toasts, GUINT_TO_POINTER(payload->id), toast);
    gtk_widget_show_all(window);
    reposition_toasts();
}

static GHashTable *parse_action_metadata(const gchar *actions_json) {
    GHashTable *metadata = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, (GDestroyNotify)action_entry_free);
    gchar *array_json = NULL;
    const gchar *cursor = NULL;
    if (actions_json == NULL || *actions_json == '\0') {
        return metadata;
    }
    array_json = g_strdup(actions_json);
    cursor = array_json;
    while ((cursor = strchr(cursor, '{')) != NULL) {
        gint depth = 0;
        gboolean in_string = FALSE;
        gboolean escaped = FALSE;
        const gchar *end = NULL;
        for (const gchar *scan = cursor; *scan != '\0'; ++scan) {
            gchar ch = *scan;
            if (escaped) {
                escaped = FALSE;
                continue;
            }
            if (ch == '\\') {
                escaped = TRUE;
                continue;
            }
            if (ch == '"') {
                in_string = !in_string;
                continue;
            }
            if (in_string) {
                continue;
            }
            if (ch == '{') {
                depth += 1;
            } else if (ch == '}') {
                depth -= 1;
                if (depth == 0) {
                    end = scan;
                    break;
                }
            }
        }
        if (end == NULL) {
            break;
        }
        gchar *object_json = g_strndup(cursor, (gsize)(end - cursor + 1));
        ActionEntry *entry = g_new0(ActionEntry, 1);
        entry->key = json_string_value(object_json, "key");
        entry->action = json_string_value(object_json, "action");
        entry->label = json_string_value(object_json, "label");
        entry->url = json_string_value(object_json, "url");
        entry->method = json_string_value(object_json, "method");
        entry->body = json_string_value(object_json, "body");
        entry->value = json_string_value(object_json, "value");
        entry->clear = json_bool_value(object_json, "clear", FALSE);
        if (entry->key != NULL && *entry->key != '\0') {
            g_hash_table_insert(metadata, g_strdup(entry->key), entry);
        } else {
            action_entry_free(entry);
        }
        g_free(object_json);
        cursor = end + 1;
    }
    g_free(array_json);
    return metadata;
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
    gint32 expire_timeout = 10000;

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
    payload->app_icon = g_strdup(app_icon);
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
        GHashTable *metadata = NULL;
        gchar *actions_json = NULL;
        GVariantIter hints_iter;
        const gchar *hint_key = NULL;
        GVariant *hint_value = NULL;
        g_variant_iter_init(&hints_iter, hints_variant);
        while (g_variant_iter_next(&hints_iter, "{&sv}", &hint_key, &hint_value)) {
            if (g_strcmp0(hint_key, "x-hanauta-ntfy-actions") == 0 && g_variant_is_of_type(hint_value, G_VARIANT_TYPE_STRING)) {
                actions_json = g_strdup(g_variant_get_string(hint_value, NULL));
            } else if (g_strcmp0(hint_key, "desktop-entry") == 0 && g_variant_is_of_type(hint_value, G_VARIANT_TYPE_STRING)) {
                g_free(payload->desktop_entry);
                payload->desktop_entry = g_strdup(g_variant_get_string(hint_value, NULL));
            } else if (g_strcmp0(hint_key, "sender-pid") == 0 && g_variant_is_of_type(hint_value, G_VARIANT_TYPE_UINT32)) {
                payload->sender_pid = g_variant_get_uint32(hint_value);
            } else if (g_strcmp0(hint_key, "sender-pid") == 0 && g_variant_is_of_type(hint_value, G_VARIANT_TYPE_INT32)) {
                gint32 raw_pid = g_variant_get_int32(hint_value);
                payload->sender_pid = raw_pid > 0 ? (guint)raw_pid : 0;
            } else if (
                (g_strcmp0(hint_key, "image-path") == 0 || g_strcmp0(hint_key, "image_path") == 0) &&
                g_variant_is_of_type(hint_value, G_VARIANT_TYPE_STRING)
            ) {
                const gchar *image_path = g_variant_get_string(hint_value, NULL);
                if (image_path != NULL && *image_path != '\0') {
                    g_free(payload->image_path);
                    payload->image_path = g_strdup(image_path);
                }
            } else if (
                g_strcmp0(hint_key, "image-data") == 0 ||
                g_strcmp0(hint_key, "image_data") == 0 ||
                g_strcmp0(hint_key, "icon_data") == 0
            ) {
                GdkPixbuf *pixbuf = pixbuf_from_image_data_variant(hint_value);
                if (pixbuf != NULL) {
                    if (payload->image_pixbuf != NULL) {
                        g_object_unref(payload->image_pixbuf);
                    }
                    payload->image_pixbuf = pixbuf;
                }
            }
            g_variant_unref(hint_value);
        }
        metadata = parse_action_metadata(actions_json);
        for (guint i = 0; i < payload->actions->len; ++i) {
            ActionEntry *action = g_ptr_array_index(payload->actions, i);
            ActionEntry *rich = g_hash_table_lookup(metadata, action->key);
            if (rich == NULL) {
                continue;
            }
            g_free(action->action);
            g_free(action->url);
            g_free(action->method);
            g_free(action->body);
            g_free(action->value);
            if (rich->label != NULL && *rich->label != '\0') {
                g_free(action->label);
                action->label = g_strdup(rich->label);
            }
            action->action = g_strdup(rich->action);
            action->url = g_strdup(rich->url);
            action->method = g_strdup(rich->method);
            action->body = g_strdup(rich->body);
            action->value = g_strdup(rich->value);
            action->clear = rich->clear;
        }
        g_hash_table_unref(metadata);
        g_free(actions_json);
        g_variant_unref(hints_variant);
    }
    {
        gint minimum_duration_ms = load_default_notification_duration_ms();
        if (payload->expire_timeout <= 0 || payload->expire_timeout < minimum_duration_ms) {
            payload->expire_timeout = minimum_duration_ms;
        }
    }
    return payload;
}

static void handle_notify(GDBusMethodInvocation *invocation, GVariant *parameters) {
    NotificationPayload *payload = payload_from_variant(parameters);
    if (!should_ignore_notification(payload)) {
        apply_app_aliases(payload);
        append_history(payload);
        if (!is_paused()) {
            dismiss_toast(payload->id, 3);
            show_toast(payload);
        }
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
    gdk_set_program_class("HanautaNotification");
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
