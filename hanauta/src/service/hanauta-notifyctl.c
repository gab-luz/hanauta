#define _POSIX_C_SOURCE 200809L

#include <gio/gio.h>
#include <glib.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>

static gchar *state_dir_path(void) {
    return g_build_filename(g_get_home_dir(), ".local", "state", "hanauta", "notification-daemon", NULL);
}

static gchar *history_file_path(void) {
    gchar *state_dir = state_dir_path();
    gchar *path = g_build_filename(state_dir, "history.json", NULL);
    g_free(state_dir);
    return path;
}

static gchar *control_file_path(void) {
    gchar *state_dir = state_dir_path();
    gchar *path = g_build_filename(state_dir, "control.json", NULL);
    g_free(state_dir);
    return path;
}

static void ensure_state_dir(void) {
    gchar *state_dir = state_dir_path();
    g_mkdir_with_parents(state_dir, 0755);
    g_free(state_dir);
}

static gboolean load_paused(void) {
    gboolean paused = FALSE;
    gchar *contents = NULL;
    gsize length = 0;
    gchar *path = control_file_path();
    if (g_file_get_contents(path, &contents, &length, NULL) && contents != NULL) {
        paused = (strstr(contents, "true") != NULL);
    }
    g_free(contents);
    g_free(path);
    return paused;
}

static gboolean save_paused(gboolean paused, GError **error) {
    gchar *path = control_file_path();
    const gchar *json_true = "{\n  \"paused\": true\n}\n";
    const gchar *json_false = "{\n  \"paused\": false\n}\n";
    ensure_state_dir();
    gboolean ok = g_file_set_contents(path, paused ? json_true : json_false, -1, error);
    g_free(path);
    return ok;
}

static gboolean write_empty_history(GError **error) {
    gchar *path = history_file_path();
    ensure_state_dir();
    gboolean ok = g_file_set_contents(path, "{\n  \"data\": [\n    []\n  ]\n}\n", -1, error);
    g_free(path);
    return ok;
}

static int command_history(void) {
    gchar *path = history_file_path();
    gchar *contents = NULL;
    gsize length = 0;
    if (!g_file_get_contents(path, &contents, &length, NULL) || contents == NULL) {
        g_print("{\"data\":[[]]}\n");
    } else {
        g_print("%s", contents);
        if (length == 0 || contents[length - 1] != '\n') {
            g_print("\n");
        }
    }
    g_free(contents);
    g_free(path);
    return 0;
}

static int command_close(const gchar *id_text) {
    GError *error = NULL;
    guint32 notification_id = (guint32)g_ascii_strtoull(id_text, NULL, 10);
    GDBusConnection *connection = g_bus_get_sync(G_BUS_TYPE_SESSION, NULL, &error);
    if (connection == NULL) {
        g_printerr("%s\n", error != NULL ? error->message : "Could not connect to the session bus.");
        g_clear_error(&error);
        return 1;
    }
    GVariant *result = g_dbus_connection_call_sync(
        connection,
        "org.freedesktop.Notifications",
        "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications",
        "CloseNotification",
        g_variant_new("(u)", notification_id),
        NULL,
        G_DBUS_CALL_FLAGS_NONE,
        3000,
        NULL,
        &error
    );
    if (result == NULL) {
        g_printerr("%s\n", error != NULL ? error->message : "CloseNotification failed.");
        g_clear_error(&error);
        g_object_unref(connection);
        return 1;
    }
    g_variant_unref(result);
    g_object_unref(connection);
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        return 1;
    }
    if (g_strcmp0(argv[1], "is-paused") == 0) {
        g_print(load_paused() ? "true\n" : "false\n");
        return 0;
    }
    if (g_strcmp0(argv[1], "set-paused") == 0) {
        gboolean value = FALSE;
        GError *error = NULL;
        if (argc < 3) {
            return 1;
        }
        value = g_ascii_strcasecmp(argv[2], "true") == 0
            || g_ascii_strcasecmp(argv[2], "1") == 0
            || g_ascii_strcasecmp(argv[2], "yes") == 0
            || g_ascii_strcasecmp(argv[2], "on") == 0;
        if (!save_paused(value, &error)) {
            g_printerr("%s\n", error != NULL ? error->message : "Could not save pause state.");
            g_clear_error(&error);
            return 1;
        }
        return 0;
    }
    if (g_strcmp0(argv[1], "history") == 0) {
        return command_history();
    }
    if (g_strcmp0(argv[1], "history-clear") == 0) {
        GError *error = NULL;
        if (!write_empty_history(&error)) {
            g_printerr("%s\n", error != NULL ? error->message : "Could not clear history.");
            g_clear_error(&error);
            return 1;
        }
        return 0;
    }
    if (g_strcmp0(argv[1], "close") == 0) {
        if (argc < 3) {
            return 1;
        }
        return command_close(argv[2]);
    }
    return 1;
}
