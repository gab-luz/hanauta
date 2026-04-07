#define _POSIX_C_SOURCE 200809L

#include <gio/gio.h>
#include <glib.h>
#include <glib/gstdio.h>
#include <stdbool.h>
#include <string.h>

typedef struct {
    gchar *settings_path;
    gchar *state_dir;
    gchar *weather_path;
    gchar *crypto_path;
    gchar *wifi_path;
    gchar *home_assistant_path;
    gchar *status_path;
    GFileMonitor *settings_monitor;
    guint heartbeat_source;
    guint refresh_source;
    gchar *ntfy_topic_key;
    gint64 ntfy_since_time;
    gboolean ntfy_cursor_ready;
    gint64 ntfy_topics_checked_at;
    GPtrArray *ntfy_all_topics_cache;
    GHashTable *ntfy_seen_ids;
    GHashTable *plugin_task_next_run;
} HanautaService;

static HanautaService g_service = {0};

typedef struct {
    gchar *key;
    gchar *action;
    gchar *label;
    gchar *url;
    gchar *method;
    gchar *body;
    gchar *value;
    gboolean clear;
} NtfyActionSpec;

typedef struct {
    gchar *plugin_id;
    gchar *plugin_dir;
    gchar *task_id;
    gint interval_seconds;
    gint timeout_seconds;
    gchar *working_dir;
    GPtrArray *command;
} PluginTaskSpec;

static gint compare_strings(gconstpointer a, gconstpointer b) {
    return g_strcmp0(*(const gchar * const *)a, *(const gchar * const *)b);
}

static gchar *escape_json_string(const gchar *text) {
    gchar *escaped = g_strescape(text != NULL ? text : "", NULL);
    gchar *quoted = g_strdup_printf("\"%s\"", escaped != NULL ? escaped : "");
    g_free(escaped);
    return quoted;
}

static gchar *load_file_text(const gchar *path) {
    gchar *contents = NULL;
    if (!g_file_get_contents(path, &contents, NULL, NULL)) {
        return g_strdup("");
    }
    return contents;
}

static gchar *extract_object_block(const gchar *json, const gchar *key) {
    gchar *pattern = g_strdup_printf("\"%s\"", key);
    const gchar *found = g_strstr_len(json, -1, pattern);
    const gchar *brace = NULL;
    gint depth = 0;
    gboolean in_string = FALSE;
    gboolean escaped = FALSE;
    gchar *result = NULL;
    const gchar *cursor = NULL;
    g_free(pattern);
    if (found == NULL) {
        return NULL;
    }
    brace = strchr(found, '{');
    if (brace == NULL) {
        return NULL;
    }
    for (cursor = brace; *cursor != '\0'; ++cursor) {
        gchar ch = *cursor;
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
                result = g_strndup(brace, (gsize)(cursor - brace + 1));
                break;
            }
        }
    }
    return result;
}

static gchar *extract_array_block(const gchar *json, const gchar *key) {
    gchar *pattern = g_strdup_printf("\"%s\"", key);
    const gchar *found = g_strstr_len(json, -1, pattern);
    const gchar *bracket = NULL;
    gint depth = 0;
    gboolean in_string = FALSE;
    gboolean escaped = FALSE;
    gchar *result = NULL;
    const gchar *cursor = NULL;
    g_free(pattern);
    if (found == NULL) {
        return NULL;
    }
    bracket = strchr(found, '[');
    if (bracket == NULL) {
        return NULL;
    }
    for (cursor = bracket; *cursor != '\0'; ++cursor) {
        gchar ch = *cursor;
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
        if (ch == '[') {
            depth += 1;
        } else if (ch == ']') {
            depth -= 1;
            if (depth == 0) {
                result = g_strndup(bracket, (gsize)(cursor - bracket + 1));
                break;
            }
        }
    }
    return result;
}

static gboolean object_bool(const gchar *object_json, const gchar *key, gboolean fallback) {
    gchar *pattern = g_strdup_printf("\"%s\"", key);
    const gchar *found = g_strstr_len(object_json, -1, pattern);
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
    while (*cursor == ' ' || *cursor == '\t' || *cursor == '\n' || *cursor == '\r') {
        cursor += 1;
    }
    if (g_str_has_prefix(cursor, "true")) {
        result = TRUE;
    } else if (g_str_has_prefix(cursor, "false")) {
        result = FALSE;
    }
    return result;
}

static gchar *object_string(const gchar *object_json, const gchar *key, const gchar *fallback) {
    gchar *pattern = g_strdup_printf("\"%s\"", key);
    const gchar *found = g_strstr_len(object_json, -1, pattern);
    const gchar *cursor = NULL;
    GString *text = NULL;
    gboolean escaped = FALSE;
    gchar *result = NULL;
    g_free(pattern);
    if (found == NULL) {
        return g_strdup(fallback);
    }
    cursor = strchr(found, ':');
    if (cursor == NULL) {
        return g_strdup(fallback);
    }
    cursor += 1;
    while (*cursor == ' ' || *cursor == '\t' || *cursor == '\n' || *cursor == '\r') {
        cursor += 1;
    }
    if (*cursor != '"') {
        return g_strdup(fallback);
    }
    cursor += 1;
    text = g_string_new("");
    while (*cursor != '\0') {
        if (escaped) {
            g_string_append_c(text, *cursor);
            escaped = FALSE;
        } else if (*cursor == '\\') {
            escaped = TRUE;
        } else if (*cursor == '"') {
            break;
        } else {
            g_string_append_c(text, *cursor);
        }
        cursor += 1;
    }
    result = g_string_free(text, FALSE);
    return result;
}

static GPtrArray *object_string_array(const gchar *object_json, const gchar *key) {
    gchar *pattern = g_strdup_printf("\"%s\"", key);
    const gchar *found = g_strstr_len(object_json, -1, pattern);
    const gchar *cursor = NULL;
    GPtrArray *values = g_ptr_array_new_with_free_func(g_free);
    gboolean in_string = FALSE;
    gboolean escaped = FALSE;
    GString *current = NULL;
    g_free(pattern);
    if (found == NULL) {
        return values;
    }
    cursor = strchr(found, ':');
    if (cursor == NULL) {
        return values;
    }
    cursor += 1;
    while (*cursor == ' ' || *cursor == '\t' || *cursor == '\n' || *cursor == '\r') {
        cursor += 1;
    }
    if (*cursor != '[') {
        return values;
    }
    cursor += 1;
    while (*cursor != '\0') {
        gchar ch = *cursor;
        if (escaped) {
            if (current != NULL) {
                g_string_append_c(current, ch);
            }
            escaped = FALSE;
        } else if (ch == '\\') {
            escaped = TRUE;
        } else if (ch == '"') {
            if (!in_string) {
                current = g_string_new("");
                in_string = TRUE;
            } else {
                gchar *value = g_string_free(current, FALSE);
                g_strstrip(value);
                if (*value != '\0') {
                    g_ptr_array_add(values, value);
                } else {
                    g_free(value);
                }
                current = NULL;
                in_string = FALSE;
            }
        } else if (in_string) {
            g_string_append_c(current, ch);
        } else if (ch == ']') {
            break;
        }
        cursor += 1;
    }
    if (current != NULL) {
        g_string_free(current, TRUE);
    }
    return values;
}

static gdouble object_number(const gchar *object_json, const gchar *key, gdouble fallback) {
    gchar *pattern = g_strdup_printf("\"%s\"", key);
    const gchar *found = g_strstr_len(object_json, -1, pattern);
    const gchar *cursor = NULL;
    gchar *end = NULL;
    gdouble value = fallback;
    g_free(pattern);
    if (found == NULL) {
        return fallback;
    }
    cursor = strchr(found, ':');
    if (cursor == NULL) {
        return fallback;
    }
    cursor += 1;
    while (*cursor == ' ' || *cursor == '\t' || *cursor == '\n' || *cursor == '\r') {
        cursor += 1;
    }
    value = g_ascii_strtod(cursor, &end);
    if (end == cursor) {
        return fallback;
    }
    return value;
}

static gchar *run_capture(GError **error, const gchar * const *argv) {
    GSubprocess *process = g_subprocess_newv(argv, G_SUBPROCESS_FLAGS_STDOUT_PIPE | G_SUBPROCESS_FLAGS_STDERR_PIPE, error);
    gchar *stdout_text = NULL;
    gchar *stderr_text = NULL;
    if (process == NULL) {
        return NULL;
    }
    if (!g_subprocess_communicate_utf8(process, NULL, NULL, &stdout_text, &stderr_text, error)) {
        g_clear_object(&process);
        g_free(stderr_text);
        return NULL;
    }
    if (!g_subprocess_get_successful(process)) {
        g_set_error(
            error,
            G_IO_ERROR,
            G_IO_ERROR_FAILED,
            "%s",
            (stderr_text != NULL && *stderr_text != '\0') ? stderr_text : "Subprocess failed."
        );
        g_clear_object(&process);
        g_free(stdout_text);
        g_free(stderr_text);
        return NULL;
    }
    g_clear_object(&process);
    g_free(stderr_text);
    return stdout_text;
}

static void ntfy_seen_ids_clear(void) {
    if (g_service.ntfy_seen_ids != NULL) {
        g_hash_table_remove_all(g_service.ntfy_seen_ids);
    }
}

static void replace_string_array(GPtrArray **target, GPtrArray *replacement) {
    if (*target != NULL) {
        g_ptr_array_free(*target, TRUE);
    }
    *target = replacement;
}

static void ntfy_action_spec_free(gpointer data) {
    NtfyActionSpec *action = data;
    if (action == NULL) {
        return;
    }
    g_free(action->key);
    g_free(action->action);
    g_free(action->label);
    g_free(action->url);
    g_free(action->method);
    g_free(action->body);
    g_free(action->value);
    g_free(action);
}

static void plugin_task_spec_free(gpointer data) {
    PluginTaskSpec *task = data;
    if (task == NULL) {
        return;
    }
    g_free(task->plugin_id);
    g_free(task->plugin_dir);
    g_free(task->task_id);
    g_free(task->working_dir);
    if (task->command != NULL) {
        g_ptr_array_free(task->command, TRUE);
    }
    g_free(task);
}

static gchar *replace_token(const gchar *text, const gchar *token, const gchar *replacement) {
    GString *result = NULL;
    const gchar *cursor = NULL;
    const gchar *found = NULL;
    gsize token_len = 0;
    if (text == NULL) {
        return g_strdup("");
    }
    if (token == NULL || *token == '\0') {
        return g_strdup(text);
    }
    token_len = strlen(token);
    result = g_string_new("");
    cursor = text;
    while ((found = g_strstr_len(cursor, -1, token)) != NULL) {
        g_string_append_len(result, cursor, (gssize)(found - cursor));
        g_string_append(result, replacement != NULL ? replacement : "");
        cursor = found + token_len;
    }
    g_string_append(result, cursor);
    return g_string_free(result, FALSE);
}

static gchar *expand_plugin_token_string(const gchar *text, const gchar *plugin_dir) {
    gchar *step = replace_token(text, "${PLUGIN_DIR}", plugin_dir != NULL ? plugin_dir : "");
    gchar *expanded = replace_token(step, "${HOME}", g_get_home_dir());
    g_free(step);
    return expanded;
}

static GPtrArray *collect_plugin_dirs(void) {
    GPtrArray *dirs = g_ptr_array_new_with_free_func(g_free);
    GHashTable *seen = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);
    const gchar *home = g_get_home_dir();
    gchar *roots[2] = {
        g_build_filename(home, ".config", "i3", "hanauta", "plugins", NULL),
        g_build_filename(home, "dev", NULL),
    };
    for (guint i = 0; i < G_N_ELEMENTS(roots); ++i) {
        GDir *dir = NULL;
        const gchar *name = NULL;
        if (roots[i] == NULL || !g_file_test(roots[i], G_FILE_TEST_IS_DIR)) {
            continue;
        }
        dir = g_dir_open(roots[i], 0, NULL);
        if (dir == NULL) {
            continue;
        }
        while ((name = g_dir_read_name(dir)) != NULL) {
            gchar *candidate = g_build_filename(roots[i], name, NULL);
            gchar *manifest = NULL;
            gchar *resolved = NULL;
            if (!g_file_test(candidate, G_FILE_TEST_IS_DIR)) {
                g_free(candidate);
                continue;
            }
            if (i == 1 && !g_str_has_prefix(name, "hanauta-plugin-")) {
                g_free(candidate);
                continue;
            }
            manifest = g_build_filename(candidate, "hanauta-service-plugin.json", NULL);
            if (!g_file_test(manifest, G_FILE_TEST_EXISTS)) {
                g_free(manifest);
                g_free(candidate);
                continue;
            }
            g_free(manifest);
            resolved = g_canonicalize_filename(candidate, NULL);
            if (!g_hash_table_contains(seen, resolved)) {
                g_hash_table_add(seen, g_strdup(resolved));
                g_ptr_array_add(dirs, resolved);
            } else {
                g_free(resolved);
            }
            g_free(candidate);
        }
        g_dir_close(dir);
    }
    g_free(roots[0]);
    g_free(roots[1]);
    g_hash_table_unref(seen);
    return dirs;
}

static void write_status_json(const gchar *status, const gchar *details) {
    gchar *status_q = escape_json_string(status);
    gchar *details_q = escape_json_string(details);
    GDateTime *now = g_date_time_new_now_local();
    gchar *updated_at = g_date_time_format(now, "%Y-%m-%dT%H:%M:%S%z");
    gchar *updated_q = escape_json_string(updated_at);
    gchar *json = g_strdup_printf(
        "{\n"
        "  \"service\": \"hanauta-service\",\n"
        "  \"status\": %s,\n"
        "  \"details\": %s,\n"
        "  \"updated_at\": %s,\n"
        "  \"weather_cache\": \"service/weather.json\",\n"
        "  \"crypto_cache\": \"service/crypto.json\",\n"
        "  \"wifi_cache\": \"service/wifi.json\",\n"
        "  \"home_assistant_cache\": \"service/home_assistant.json\"\n"
        "}\n",
        status_q,
        details_q,
        updated_q
    );
    g_file_set_contents(g_service.status_path, json, -1, NULL);
    g_free(status_q);
    g_free(details_q);
    g_free(updated_q);
    g_free(updated_at);
    g_free(json);
    g_date_time_unref(now);
}

static gboolean refresh_weather(void) {
    gchar *settings = load_file_text(g_service.settings_path);
    gchar *weather_obj = extract_object_block(settings, "weather");
    gchar *lat_text = NULL;
    gchar *lon_text = NULL;
    gchar *timezone = NULL;
    gchar *timezone_uri = NULL;
    gchar *name = NULL;
    gchar *admin1 = NULL;
    gchar *country = NULL;
    GError *error = NULL;
    gchar *payload = NULL;
    gchar *url = NULL;
    gchar *requested = NULL;
    gchar *updated_at = NULL;
    gchar *json = NULL;
    gchar *timezone_q = NULL;
    gchar *name_q = NULL;
    gchar *admin1_q = NULL;
    gchar *country_q = NULL;
    GDateTime *now = NULL;
    gboolean ok = FALSE;

    if (weather_obj == NULL || !object_bool(weather_obj, "enabled", FALSE)) {
        goto cleanup;
    }

    lat_text = g_strdup_printf("%.5f", object_number(weather_obj, "latitude", 0.0));
    lon_text = g_strdup_printf("%.5f", object_number(weather_obj, "longitude", 0.0));
    timezone = object_string(weather_obj, "timezone", "auto");
    name = object_string(weather_obj, "name", "");
    admin1 = object_string(weather_obj, "admin1", "");
    country = object_string(weather_obj, "country", "");

    url = g_strdup_printf(
        "https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&timezone=%s&forecast_days=7&current=temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,pressure_msl,weather_code,wind_speed_10m,is_day&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
        lat_text,
        lon_text,
        timezone_uri = g_uri_escape_string(timezone, NULL, TRUE)
    );

    const gchar *argv[] = {"curl", "-fsSL", "-H", "User-Agent: HanautaService/1.0", url, NULL};
    payload = run_capture(&error, argv);
    if (payload == NULL) {
        write_status_json("degraded", error != NULL ? error->message : "Weather refresh failed.");
        g_clear_error(&error);
        goto cleanup;
    }

    requested = g_strdup_printf(
        "    \"requested\": {\n"
        "      \"latitude\": %s,\n"
        "      \"longitude\": %s,\n"
        "      \"timezone\": %s,\n"
        "      \"name\": %s,\n"
        "      \"admin1\": %s,\n"
        "      \"country\": %s\n"
        "    }",
        lat_text,
        lon_text,
        timezone_q = escape_json_string(timezone),
        name_q = escape_json_string(name),
        admin1_q = escape_json_string(admin1),
        country_q = escape_json_string(country)
    );
    now = g_date_time_new_now_local();
    updated_at = g_date_time_format(now, "%Y-%m-%dT%H:%M:%S%z");
    json = g_strdup_printf(
        "{\n"
        "  \"source\": \"open-meteo\",\n"
        "  \"updated_at\": \"%s\",\n"
        "%s,\n"
        "  \"payload\": %s\n"
        "}\n",
        updated_at,
        requested,
        payload
    );
    ok = g_file_set_contents(g_service.weather_path, json, -1, NULL);

cleanup:
    g_free(settings);
    g_free(weather_obj);
    g_free(lat_text);
    g_free(lon_text);
    g_free(timezone);
    g_free(timezone_uri);
    g_free(name);
    g_free(admin1);
    g_free(country);
    g_free(payload);
    g_free(url);
    g_free(requested);
    g_free(updated_at);
    g_free(json);
    g_free(timezone_q);
    g_free(name_q);
    g_free(admin1_q);
    g_free(country_q);
    if (now != NULL) {
        g_date_time_unref(now);
    }
    return ok;
}

static gboolean refresh_wifi(void) {
    const gchar *scan_argv[] = {
        "nmcli",
        "-t",
        "-f",
        "IN-USE,SSID,SIGNAL,SECURITY",
        "dev",
        "wifi",
        "list",
        "--rescan",
        "auto",
        NULL
    };
    const gchar *radio_argv[] = {"nmcli", "radio", "wifi", NULL};
    gchar *scan_output = NULL;
    gchar *radio_output = NULL;
    gchar *updated_at = NULL;
    gchar *current_q = NULL;
    gchar *radio_q = NULL;
    gchar *json = NULL;
    GDateTime *now = NULL;
    GString *networks = g_string_new("[\n");
    GHashTable *seen = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);
    GError *error = NULL;
    gchar *current_ssid = g_strdup("");
    gboolean radio_enabled = FALSE;
    gboolean first = TRUE;
    gboolean ok = FALSE;

    scan_output = run_capture(&error, scan_argv);
    if (scan_output == NULL) {
        write_status_json("degraded", error != NULL ? error->message : "Wi-Fi scan failed.");
        g_clear_error(&error);
        goto cleanup;
    }

    radio_output = run_capture(&error, radio_argv);
    if (radio_output == NULL) {
        write_status_json("degraded", error != NULL ? error->message : "Wi-Fi radio state refresh failed.");
        g_clear_error(&error);
        goto cleanup;
    }
    radio_enabled = g_ascii_strcasecmp(g_strstrip(radio_output), "enabled") == 0;

    gchar **lines = g_strsplit(scan_output, "\n", -1);
    for (gchar **line = lines; line != NULL && *line != NULL; ++line) {
        gchar *trimmed = g_strstrip(*line);
        gchar **parts = NULL;
        gchar *ssid = NULL;
        const gchar *in_use = NULL;
        gint signal = 0;
        gchar *security = NULL;
        gchar *ssid_q = NULL;
        gchar *security_q = NULL;
        gboolean secure = FALSE;

        if (trimmed[0] == '\0') {
            continue;
        }

        parts = g_strsplit(trimmed, ":", 4);
        if (g_strv_length(parts) < 4) {
            g_strfreev(parts);
            continue;
        }

        in_use = g_strstrip(parts[0]);
        ssid = g_strdup(g_strstrip(parts[1]));
        g_strdelimit(ssid, "\\", '\\');
        if (ssid[0] == '\0' || g_hash_table_contains(seen, ssid)) {
            g_free(ssid);
            g_strfreev(parts);
            continue;
        }
        g_hash_table_add(seen, g_strdup(ssid));
        if (g_strcmp0(in_use, "*") == 0) {
            g_free(current_ssid);
            current_ssid = g_strdup(ssid);
        }
        signal = (gint)g_ascii_strtoll(g_strstrip(parts[2]), NULL, 10);
        security = g_strdup(g_strstrip(parts[3]));
        secure = security[0] != '\0' && g_strcmp0(security, "--") != 0;

        ssid_q = escape_json_string(ssid);
        security_q = escape_json_string(security[0] != '\0' ? security : "--");
        g_string_append_printf(
            networks,
            "%s    {\n"
            "      \"ssid\": %s,\n"
            "      \"signal\": %d,\n"
            "      \"security\": %s,\n"
            "      \"in_use\": %s,\n"
            "      \"secure\": %s\n"
            "    }",
            first ? "" : ",\n",
            ssid_q,
            signal,
            security_q,
            g_strcmp0(in_use, "*") == 0 ? "true" : "false",
            secure ? "true" : "false"
        );
        first = FALSE;

        g_free(ssid);
        g_free(security);
        g_free(ssid_q);
        g_free(security_q);
        g_strfreev(parts);
    }
    g_strfreev(lines);
    g_string_append(networks, "\n  ]");

    now = g_date_time_new_now_local();
    updated_at = g_date_time_format(now, "%Y-%m-%dT%H:%M:%S%z");
    current_q = escape_json_string(current_ssid);
    radio_q = escape_json_string(radio_enabled ? "enabled" : "disabled");
    json = g_strdup_printf(
        "{\n"
        "  \"source\": \"nmcli\",\n"
        "  \"updated_at\": \"%s\",\n"
        "  \"current_ssid\": %s,\n"
        "  \"radio\": %s,\n"
        "  \"networks\": %s\n"
        "}\n",
        updated_at,
        current_q,
        radio_q,
        networks->str
    );
    ok = g_file_set_contents(g_service.wifi_path, json, -1, NULL);

cleanup:
    g_free(scan_output);
    g_free(radio_output);
    g_free(updated_at);
    g_free(current_q);
    g_free(radio_q);
    g_free(json);
    g_free(current_ssid);
    if (now != NULL) {
        g_date_time_unref(now);
    }
    if (networks != NULL) {
        g_string_free(networks, TRUE);
    }
    if (seen != NULL) {
        g_hash_table_unref(seen);
    }
    g_clear_error(&error);
    return ok;
}

static GPtrArray *split_coin_ids(const gchar *text) {
    GPtrArray *coins = g_ptr_array_new_with_free_func(g_free);
    gchar **pieces = g_strsplit(text, ",", -1);
    if (pieces == NULL) {
        return coins;
    }
    for (gchar **part = pieces; *part != NULL; ++part) {
        gchar *trimmed = g_strdup(g_strstrip(*part));
        if (trimmed[0] == '\0') {
            g_free(trimmed);
            continue;
        }
        g_ptr_array_add(coins, trimmed);
    }
    g_strfreev(pieces);
    return coins;
}

static gboolean refresh_crypto(void) {
    gchar *settings = load_file_text(g_service.settings_path);
    gchar *crypto_obj = extract_object_block(settings, "crypto");
    gchar *services_obj = extract_object_block(settings, "services");
    gchar *service_obj = NULL;
    gchar *coins_text = NULL;
    gchar *currency = NULL;
    gchar *api_key = NULL;
    GPtrArray *coins = NULL;
    gchar *joined_ids = NULL;
    gchar *tracked = NULL;
    gchar *ids_uri = NULL;
    gchar *currency_uri = NULL;
    gchar *payload = NULL;
    gchar *updated_at = NULL;
    gchar *json = NULL;
    gchar *currency_q = NULL;
    GDateTime *now = NULL;
    GString *url = NULL;
    GError *error = NULL;
    gboolean ok = FALSE;

    if (services_obj != NULL) {
        service_obj = extract_object_block(services_obj, "crypto_widget");
    }
    if (service_obj != NULL && !object_bool(service_obj, "enabled", TRUE)) {
        goto cleanup;
    }
    if (crypto_obj == NULL) {
        goto cleanup;
    }

    coins_text = object_string(crypto_obj, "tracked_coins", "bitcoin,ethereum");
    currency = object_string(crypto_obj, "vs_currency", "usd");
    api_key = object_string(crypto_obj, "api_key", "");
    coins = split_coin_ids(coins_text);
    if (coins->len == 0) {
        goto cleanup;
    }

    GString *ids = g_string_new("");
    for (guint i = 0; i < coins->len; ++i) {
        const gchar *coin = g_ptr_array_index(coins, i);
        if (i > 0) {
            g_string_append_c(ids, ',');
        }
        g_string_append(ids, coin);
    }
    joined_ids = g_string_free(ids, FALSE);
    tracked = escape_json_string(joined_ids);

    url = g_string_new("https://api.coingecko.com/api/v3/simple/price?include_24hr_change=true&include_last_updated_at=true");
    ids_uri = g_uri_escape_string(joined_ids, NULL, TRUE);
    currency_uri = g_uri_escape_string(currency, NULL, TRUE);
    g_string_append_printf(url, "&ids=%s&vs_currencies=%s", ids_uri, currency_uri);

    if (api_key != NULL && api_key[0] != '\0') {
        const gchar *argv[] = {"curl", "-fsSL", "-H", "accept: application/json", "-H", NULL, NULL, NULL};
        gchar *auth = g_strdup_printf("x-cg-demo-api-key: %s", api_key);
        argv[4] = auth;
        argv[5] = url->str;
        payload = run_capture(&error, argv);
        g_free(auth);
    } else {
        const gchar *argv[] = {"curl", "-fsSL", "-H", "accept: application/json", url->str, NULL};
        payload = run_capture(&error, argv);
    }

    if (payload == NULL) {
        write_status_json("degraded", error != NULL ? error->message : "Crypto refresh failed.");
        g_clear_error(&error);
        goto cleanup;
    }

    now = g_date_time_new_now_local();
    updated_at = g_date_time_format(now, "%Y-%m-%dT%H:%M:%S%z");
    json = g_strdup_printf(
        "{\n"
        "  \"source\": \"coingecko\",\n"
        "  \"updated_at\": \"%s\",\n"
        "  \"vs_currency\": %s,\n"
        "  \"tracked_coins\": %s,\n"
        "  \"payload\": %s\n"
        "}\n",
        updated_at,
        currency_q = escape_json_string(currency),
        tracked,
        payload
    );
    ok = g_file_set_contents(g_service.crypto_path, json, -1, NULL);

cleanup:
    g_free(settings);
    g_free(crypto_obj);
    g_free(services_obj);
    g_free(service_obj);
    g_free(coins_text);
    g_free(currency);
    g_free(api_key);
    if (coins != NULL) {
        g_ptr_array_free(coins, TRUE);
    }
    g_free(joined_ids);
    g_free(tracked);
    g_free(ids_uri);
    g_free(currency_uri);
    g_free(payload);
    g_free(updated_at);
    g_free(json);
    g_free(currency_q);
    if (url != NULL) {
        g_string_free(url, TRUE);
    }
    if (now != NULL) {
        g_date_time_unref(now);
    }
    g_clear_error(&error);
    return ok;
}

static gboolean refresh_home_assistant(void) {
    gchar *settings = load_file_text(g_service.settings_path);
    gchar *home_assistant_obj = extract_object_block(settings, "home_assistant");
    gchar *services_obj = extract_object_block(settings, "services");
    gchar *service_obj = NULL;
    gchar *base_url = NULL;
    gchar *token = NULL;
    gchar *trimmed_url = NULL;
    gchar *url_q = NULL;
    gchar *payload = NULL;
    gchar *json = NULL;
    gchar *updated_at = NULL;
    GDateTime *now = NULL;
    GError *error = NULL;
    gboolean ok = FALSE;

    if (services_obj != NULL) {
        service_obj = extract_object_block(services_obj, "home_assistant");
    }
    if (service_obj != NULL && !object_bool(service_obj, "enabled", TRUE)) {
        g_remove(g_service.home_assistant_path);
        goto cleanup;
    }
    if (home_assistant_obj == NULL) {
        g_remove(g_service.home_assistant_path);
        goto cleanup;
    }

    base_url = object_string(home_assistant_obj, "url", "");
    token = object_string(home_assistant_obj, "token", "");
    g_strstrip(base_url);
    g_strstrip(token);
    if (base_url[0] == '\0' || token[0] == '\0') {
        g_remove(g_service.home_assistant_path);
        goto cleanup;
    }

    trimmed_url = g_strdup(base_url);
    g_strstrip(trimmed_url);
    while (g_str_has_suffix(trimmed_url, "/")) {
        trimmed_url[strlen(trimmed_url) - 1] = '\0';
    }
    if (trimmed_url[0] == '\0') {
        g_remove(g_service.home_assistant_path);
        goto cleanup;
    }

    gchar *auth_header = g_strdup_printf("Authorization: Bearer %s", token);
    gchar *content_type_header = g_strdup("Content-Type: application/json");
    gchar *target_url = g_strdup_printf("%s/api/states", trimmed_url);
    const gchar *argv[] = {
        "curl",
        "-fsSL",
        "-H",
        auth_header,
        "-H",
        content_type_header,
        "-H",
        "User-Agent: HanautaService/1.0",
        target_url,
        NULL
    };
    payload = run_capture(&error, argv);
    g_free(auth_header);
    g_free(content_type_header);
    g_free(target_url);

    if (payload == NULL) {
        write_status_json("degraded", error != NULL ? error->message : "Home Assistant refresh failed.");
        g_clear_error(&error);
        goto cleanup;
    }

    now = g_date_time_new_now_local();
    updated_at = g_date_time_format(now, "%Y-%m-%dT%H:%M:%S%z");
    url_q = escape_json_string(trimmed_url);
    json = g_strdup_printf(
        "{\n"
        "  \"source\": \"home_assistant\",\n"
        "  \"updated_at\": \"%s\",\n"
        "  \"url\": %s,\n"
        "  \"payload\": %s\n"
        "}\n",
        updated_at,
        url_q,
        payload
    );
    ok = g_file_set_contents(g_service.home_assistant_path, json, -1, NULL);

cleanup:
    g_free(settings);
    g_free(home_assistant_obj);
    g_free(services_obj);
    g_free(service_obj);
    g_free(base_url);
    g_free(token);
    g_free(trimmed_url);
    g_free(url_q);
    g_free(payload);
    g_free(json);
    g_free(updated_at);
    if (now != NULL) {
        g_date_time_unref(now);
    }
    g_clear_error(&error);
    return ok;
}

static gchar *json_escape_plain(const gchar *text) {
    GString *buffer = g_string_new("");
    const gchar *cursor = text != NULL ? text : "";
    while (*cursor != '\0') {
        switch (*cursor) {
            case '\\':
                g_string_append(buffer, "\\\\");
                break;
            case '"':
                g_string_append(buffer, "\\\"");
                break;
            case '\n':
                g_string_append(buffer, "\\n");
                break;
            case '\r':
                g_string_append(buffer, "\\r");
                break;
            case '\t':
                g_string_append(buffer, "\\t");
                break;
            default:
                g_string_append_c(buffer, *cursor);
                break;
        }
        cursor += 1;
    }
    return g_string_free(buffer, FALSE);
}

static gchar *serialize_ntfy_actions_json(const GPtrArray *actions) {
    GString *json = g_string_new("[");
    if (actions != NULL) {
        for (guint i = 0; i < actions->len; ++i) {
            const NtfyActionSpec *action = g_ptr_array_index((GPtrArray *)actions, i);
            gchar *key = NULL;
            gchar *type = NULL;
            gchar *label = NULL;
            gchar *url = NULL;
            gchar *method = NULL;
            gchar *body = NULL;
            gchar *value = NULL;
            if (action == NULL || action->key == NULL || *action->key == '\0') {
                continue;
            }
            key = json_escape_plain(action->key);
            type = json_escape_plain(action->action);
            label = json_escape_plain(action->label);
            url = json_escape_plain(action->url);
            method = json_escape_plain(action->method);
            body = json_escape_plain(action->body);
            value = json_escape_plain(action->value);
            g_string_append_printf(
                json,
                "%s{\"key\":\"%s\",\"action\":\"%s\",\"label\":\"%s\",\"url\":\"%s\",\"method\":\"%s\",\"body\":\"%s\",\"value\":\"%s\",\"clear\":%s}",
                json->len > 1 ? "," : "",
                key,
                type,
                label,
                url,
                method,
                body,
                value,
                action->clear ? "true" : "false"
            );
            g_free(key);
            g_free(type);
            g_free(label);
            g_free(url);
            g_free(method);
            g_free(body);
            g_free(value);
        }
    }
    g_string_append_c(json, ']');
    return g_string_free(json, FALSE);
}

static void notify_desktop_ntfy(const gchar *summary, const gchar *body, const gchar *topic, gint priority, const GPtrArray *actions) {
    GDBusConnection *connection = NULL;
    GVariantBuilder actions_builder;
    GVariantBuilder hints_builder;
    GError *error = NULL;
    GVariant *result = NULL;
    gchar *resolved_summary = NULL;
    gchar *resolved_body = NULL;
    gchar *actions_json = NULL;
    guint8 urgency = 1;

    connection = g_bus_get_sync(G_BUS_TYPE_SESSION, NULL, &error);
    if (connection == NULL) {
        g_clear_error(&error);
        return;
    }

    resolved_summary = g_strdup((summary != NULL && *summary != '\0') ? summary : "ntfy");
    if (body != NULL && *body != '\0') {
        resolved_body = g_strdup(body);
    } else if (topic != NULL && *topic != '\0') {
        resolved_body = g_strdup_printf("New message on %s", topic);
    } else {
        resolved_body = g_strdup("New ntfy message");
    }

    if (priority >= 5) {
        urgency = 2;
    } else if (priority <= 2 && priority > 0) {
        urgency = 0;
    }

    g_variant_builder_init(&actions_builder, G_VARIANT_TYPE("as"));
    if (actions != NULL) {
        for (guint i = 0; i < actions->len; ++i) {
            const NtfyActionSpec *action = g_ptr_array_index((GPtrArray *)actions, i);
            if (action == NULL || action->key == NULL || *action->key == '\0') {
                continue;
            }
            g_variant_builder_add(&actions_builder, "s", action->key);
            g_variant_builder_add(&actions_builder, "s", (action->label != NULL && *action->label != '\0') ? action->label : action->key);
        }
    }

    g_variant_builder_init(&hints_builder, G_VARIANT_TYPE("a{sv}"));
    g_variant_builder_add(&hints_builder, "{sv}", "urgency", g_variant_new_byte(urgency));
    g_variant_builder_add(&hints_builder, "{sv}", "desktop-entry", g_variant_new_string("hanauta-ntfy"));
    if (topic != NULL && *topic != '\0') {
        g_variant_builder_add(&hints_builder, "{sv}", "x-hanauta-ntfy-topic", g_variant_new_string(topic));
    }
    if (actions != NULL && actions->len > 0) {
        actions_json = serialize_ntfy_actions_json(actions);
        g_variant_builder_add(&hints_builder, "{sv}", "x-hanauta-ntfy-actions", g_variant_new_string(actions_json));
    }

    result = g_dbus_connection_call_sync(
        connection,
        "org.freedesktop.Notifications",
        "/org/freedesktop/Notifications",
        "org.freedesktop.Notifications",
        "Notify",
        g_variant_new(
            "(susssasa{sv}i)",
            "ntfy",
            0,
            "notifications",
            resolved_summary,
            resolved_body,
            &actions_builder,
            &hints_builder,
            priority >= 5 ? 0 : 8000
        ),
        G_VARIANT_TYPE("(u)"),
        G_DBUS_CALL_FLAGS_NONE,
        3000,
        NULL,
        &error
    );
    if (result != NULL) {
        g_variant_unref(result);
    }
    g_clear_error(&error);
    g_object_unref(connection);
    g_free(actions_json);
    g_free(resolved_summary);
    g_free(resolved_body);
}

static gchar *ntfy_auth_header(const gchar *mode, const gchar *token, const gchar *username, const gchar *password) {
    gboolean has_token = token != NULL && *token != '\0';
    if (has_token || g_strcmp0(mode, "token") == 0) {
        if (!has_token) {
            return NULL;
        }
        return g_strdup_printf("Authorization: Bearer %s", token);
    }
    if ((username == NULL || *username == '\0') && (password == NULL || *password == '\0')) {
        return NULL;
    }
    gchar *credentials = g_strdup_printf("%s:%s", username != NULL ? username : "", password != NULL ? password : "");
    gchar *encoded = g_base64_encode((const guchar *)credentials, strlen(credentials));
    gchar *header = g_strdup_printf("Authorization: Basic %s", encoded);
    g_free(credentials);
    g_free(encoded);
    return header;
}

static gchar *join_topics_path(const GPtrArray *topics) {
    GString *builder = NULL;
    if (topics == NULL || topics->len == 0) {
        return g_strdup("");
    }
    builder = g_string_new("");
    for (guint i = 0; i < topics->len; ++i) {
        const gchar *topic = g_ptr_array_index((GPtrArray *)topics, i);
        gchar *escaped = NULL;
        if (topic == NULL || *topic == '\0') {
            continue;
        }
        escaped = g_uri_escape_string(topic, NULL, TRUE);
        if (builder->len > 0) {
            g_string_append_c(builder, ',');
        }
        g_string_append(builder, escaped);
        g_free(escaped);
    }
    return g_string_free(builder, FALSE);
}

static GPtrArray *parse_ntfy_topics_payload(const gchar *payload_text) {
    GPtrArray *topics = g_ptr_array_new_with_free_func(g_free);
    gchar *working = NULL;
    gchar *trimmed = NULL;
    if (payload_text == NULL || *payload_text == '\0') {
        return topics;
    }
    trimmed = g_strdup(payload_text);
    g_strstrip(trimmed);
    if (*trimmed == '[') {
        gchar *start = trimmed + 1;
        gchar *end = strrchr(start, ']');
        if (end != NULL) {
            *end = '\0';
            gchar **parts = g_strsplit(start, ",", -1);
            for (gchar **part = parts; part != NULL && *part != NULL; ++part) {
                gchar *value = g_strdup(g_strstrip(*part));
                g_strdelimit(value, "\"", ' ');
                g_strstrip(value);
                if (*value != '\0') {
                    g_ptr_array_add(topics, value);
                } else {
                    g_free(value);
                }
            }
            g_strfreev(parts);
        }
        g_ptr_array_sort(topics, compare_strings);
        g_free(trimmed);
        return topics;
    }
    if (strstr(payload_text, "\"topics\"") != NULL) {
        working = g_strdup(payload_text);
        gchar *start = strchr(working, '[');
        gchar *end = start != NULL ? strchr(start, ']') : NULL;
        if (start != NULL && end != NULL && end > start) {
            *end = '\0';
            gchar **parts = g_strsplit(start + 1, ",", -1);
            for (gchar **part = parts; part != NULL && *part != NULL; ++part) {
                gchar *value = g_strdup(g_strstrip(*part));
                g_strdelimit(value, "\"", ' ');
                g_strstrip(value);
                if (*value != '\0') {
                    g_ptr_array_add(topics, value);
                } else {
                    g_free(value);
                }
            }
            g_strfreev(parts);
        }
        g_free(working);
        g_ptr_array_sort(topics, compare_strings);
        g_free(trimmed);
        return topics;
    }
    gchar **lines = g_strsplit(payload_text, "\n", -1);
    for (gchar **line = lines; line != NULL && *line != NULL; ++line) {
        gchar *value = g_strdup(g_strstrip(*line));
        if (*value != '\0') {
            if (value[0] == '"' && value[strlen(value) - 1] == '"') {
                value[strlen(value) - 1] = '\0';
                memmove(value, value + 1, strlen(value));
            }
            if (*value != '\0') {
                g_ptr_array_add(topics, value);
            } else {
                g_free(value);
            }
        } else {
            g_free(value);
        }
    }
    g_strfreev(lines);
    g_ptr_array_sort(topics, compare_strings);
    g_free(trimmed);
    return topics;
}

static GPtrArray *parse_ntfy_action_specs(const gchar *entry_json) {
    GPtrArray *actions = g_ptr_array_new_with_free_func(ntfy_action_spec_free);
    gchar *actions_json = extract_array_block(entry_json, "actions");
    const gchar *cursor = NULL;
    if (actions_json == NULL) {
        return actions;
    }
    cursor = actions_json;
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
        NtfyActionSpec *action = g_new0(NtfyActionSpec, 1);
        action->key = object_string(object_json, "id", "");
        action->action = object_string(object_json, "action", "");
        action->label = object_string(object_json, "label", "");
        action->url = object_string(object_json, "url", "");
        action->method = object_string(object_json, "method", "");
        action->body = object_string(object_json, "body", "");
        action->value = object_string(object_json, "value", "");
        action->clear = object_bool(object_json, "clear", FALSE);
        if (action->key[0] != '\0' && action->label[0] != '\0' && action->action[0] != '\0') {
            g_ptr_array_add(actions, action);
        } else {
            ntfy_action_spec_free(action);
        }
        g_free(object_json);
        cursor = end + 1;
    }
    g_free(actions_json);
    return actions;
}

static GPtrArray *fetch_ntfy_all_topics(const gchar *server_url, const gchar *auth_mode, const gchar *token, const gchar *username, const gchar *password) {
    GPtrArray *topics = g_ptr_array_new_with_free_func(g_free);
    gchar *auth_header = NULL;
    gchar *url = NULL;
    gchar *payload = NULL;
    GError *error = NULL;
    const gchar *argv_no_auth[] = {
        "curl",
        "-fsSL",
        "--max-time",
        "8",
        "-H",
        "Accept: application/json, text/plain, */*",
        "-H",
        "User-Agent: HanautaService/1.0",
        NULL,
        NULL
    };
    const gchar *argv_auth[] = {
        "curl",
        "-fsSL",
        "--max-time",
        "8",
        "-H",
        "Accept: application/json, text/plain, */*",
        "-H",
        "User-Agent: HanautaService/1.0",
        "-H",
        NULL,
        NULL,
        NULL
    };

    if (server_url == NULL || *server_url == '\0') {
        return topics;
    }

    auth_header = ntfy_auth_header(auth_mode, token, username, password);
    url = g_strdup_printf("%s/topics", server_url);
    if (auth_header != NULL) {
        argv_auth[9] = auth_header;
        argv_auth[10] = url;
        payload = run_capture(&error, argv_auth);
    } else {
        argv_no_auth[8] = url;
        payload = run_capture(&error, argv_no_auth);
    }
    if (payload != NULL) {
        GPtrArray *parsed = parse_ntfy_topics_payload(payload);
        replace_string_array(&topics, parsed);
    }
    g_clear_error(&error);
    g_free(auth_header);
    g_free(url);
    g_free(payload);
    return topics;
}

static void ntfy_cursor_reset(const gchar *server_url, const GPtrArray *topics) {
    gchar *joined_topics = join_topics_path(topics);
    gchar *new_key = g_strdup_printf("%s|%s", server_url != NULL ? server_url : "", joined_topics);
    if (g_strcmp0(g_service.ntfy_topic_key, new_key) != 0) {
        g_free(g_service.ntfy_topic_key);
        g_service.ntfy_topic_key = new_key;
        g_service.ntfy_since_time = 0;
        g_service.ntfy_cursor_ready = FALSE;
        ntfy_seen_ids_clear();
        g_free(joined_topics);
        return;
    }
    g_free(joined_topics);
    g_free(new_key);
}

static gboolean ntfy_seen_id_recent(const gchar *message_id) {
    if (message_id == NULL || *message_id == '\0' || g_service.ntfy_seen_ids == NULL) {
        return FALSE;
    }
    return g_hash_table_contains(g_service.ntfy_seen_ids, message_id);
}

static void ntfy_mark_seen(const gchar *message_id) {
    if (message_id == NULL || *message_id == '\0' || g_service.ntfy_seen_ids == NULL) {
        return;
    }
    if (g_hash_table_size(g_service.ntfy_seen_ids) >= 1024) {
        g_hash_table_remove_all(g_service.ntfy_seen_ids);
    }
    g_hash_table_add(g_service.ntfy_seen_ids, g_strdup(message_id));
}

static gboolean refresh_ntfy(void) {
    gchar *settings = load_file_text(g_service.settings_path);
    gchar *ntfy_obj = extract_object_block(settings, "ntfy");
    gchar *server_url = NULL;
    gchar *token = NULL;
    gchar *username = NULL;
    gchar *password = NULL;
    gchar *auth_mode = NULL;
    gchar *legacy_topic = NULL;
    GPtrArray *selected_topics = NULL;
    GPtrArray *effective_topics = g_ptr_array_new_with_free_func(g_free);
    gboolean enabled = FALSE;
    gboolean all_topics = FALSE;
    gboolean hide_content = FALSE;
    gboolean ok = FALSE;

    if (ntfy_obj == NULL) {
        goto cleanup;
    }
    enabled = object_bool(ntfy_obj, "enabled", FALSE);
    if (!enabled) {
        ntfy_cursor_reset("", NULL);
        replace_string_array(&g_service.ntfy_all_topics_cache, g_ptr_array_new_with_free_func(g_free));
        goto cleanup;
    }

    server_url = object_string(ntfy_obj, "server_url", "");
    token = object_string(ntfy_obj, "token", "");
    username = object_string(ntfy_obj, "username", "");
    password = object_string(ntfy_obj, "password", "");
    auth_mode = object_string(ntfy_obj, "auth_mode", (token[0] != '\0') ? "token" : "basic");
    legacy_topic = object_string(ntfy_obj, "topic", "");
    selected_topics = object_string_array(ntfy_obj, "topics");
    all_topics = object_bool(ntfy_obj, "all_topics", FALSE);
    hide_content = object_bool(ntfy_obj, "hide_notification_content", FALSE);
    g_strstrip(server_url);
    while (g_str_has_suffix(server_url, "/")) {
        server_url[strlen(server_url) - 1] = '\0';
    }

    if (server_url[0] == '\0') {
        goto cleanup;
    }

    if (all_topics) {
        gint64 now = g_get_real_time() / G_USEC_PER_SEC;
        if (g_service.ntfy_all_topics_cache == NULL || now - g_service.ntfy_topics_checked_at >= 60) {
            GPtrArray *all = fetch_ntfy_all_topics(server_url, auth_mode, token, username, password);
            replace_string_array(&g_service.ntfy_all_topics_cache, all);
            g_service.ntfy_topics_checked_at = now;
        }
        if (g_service.ntfy_all_topics_cache != NULL) {
            for (guint i = 0; i < g_service.ntfy_all_topics_cache->len; ++i) {
                const gchar *topic = g_ptr_array_index(g_service.ntfy_all_topics_cache, i);
                if (topic != NULL && *topic != '\0') {
                    g_ptr_array_add(effective_topics, g_strdup(topic));
                }
            }
        }
    } else {
        for (guint i = 0; selected_topics != NULL && i < selected_topics->len; ++i) {
            const gchar *topic = g_ptr_array_index(selected_topics, i);
            if (topic != NULL && *topic != '\0') {
                g_ptr_array_add(effective_topics, g_strdup(topic));
            }
        }
        if (effective_topics->len == 0 && legacy_topic[0] != '\0') {
            g_ptr_array_add(effective_topics, g_strdup(legacy_topic));
        }
    }

    g_ptr_array_sort(effective_topics, compare_strings);
    ntfy_cursor_reset(server_url, effective_topics);
    if (effective_topics->len == 0) {
        ok = TRUE;
        goto cleanup;
    }

    gchar *topics_path = join_topics_path(effective_topics);
    gchar *auth_header = ntfy_auth_header(auth_mode, token, username, password);
    gchar *url = NULL;
    gchar *payload = NULL;
    GError *error = NULL;
    gint64 newest_time = g_service.ntfy_since_time;
    gboolean initial_sync = !g_service.ntfy_cursor_ready;
    const gchar *argv_no_auth[] = {
        "curl",
        "-fsSL",
        "--max-time",
        "8",
        "-H",
        "Accept: application/x-ndjson, application/json, text/plain, */*",
        "-H",
        "User-Agent: HanautaService/1.0",
        NULL,
        NULL
    };
    const gchar *argv_auth[] = {
        "curl",
        "-fsSL",
        "--max-time",
        "8",
        "-H",
        "Accept: application/x-ndjson, application/json, text/plain, */*",
        "-H",
        "User-Agent: HanautaService/1.0",
        "-H",
        NULL,
        NULL,
        NULL
    };

    if (topics_path[0] == '\0') {
        g_free(topics_path);
        g_free(auth_header);
        goto cleanup;
    }

    if (g_service.ntfy_cursor_ready && g_service.ntfy_since_time > 0) {
        url = g_strdup_printf("%s/%s/json?poll=1&since=%" G_GINT64_FORMAT, server_url, topics_path, g_service.ntfy_since_time);
    } else {
        url = g_strdup_printf("%s/%s/json?poll=1&since=latest", server_url, topics_path);
    }

    if (auth_header != NULL) {
        argv_auth[9] = auth_header;
        argv_auth[10] = url;
        payload = run_capture(&error, argv_auth);
    } else {
        argv_no_auth[8] = url;
        payload = run_capture(&error, argv_no_auth);
    }

    if (payload == NULL) {
        write_status_json("degraded", error != NULL ? error->message : "ntfy refresh failed.");
        g_clear_error(&error);
        g_free(topics_path);
        g_free(auth_header);
        g_free(url);
        goto cleanup;
    }

    gchar **lines = g_strsplit(payload, "\n", -1);
    for (gchar **line = lines; line != NULL && *line != NULL; ++line) {
        gchar *entry = g_strstrip(*line);
        gchar *event = NULL;
        gchar *message_id = NULL;
        gchar *topic = NULL;
        gchar *title = NULL;
        gchar *message = NULL;
        GPtrArray *actions = NULL;
        gchar *display_title = NULL;
        gchar *display_message = NULL;
        gint priority = 0;
        gint64 message_time = 0;
        if (*entry == '\0' || *entry != '{') {
            continue;
        }
        event = object_string(entry, "event", "");
        if (g_strcmp0(event, "message") != 0) {
            g_free(event);
            continue;
        }
        message_id = object_string(entry, "id", "");
        if (ntfy_seen_id_recent(message_id)) {
            g_free(event);
            g_free(message_id);
            continue;
        }
        topic = object_string(entry, "topic", "");
        title = object_string(entry, "title", "");
        message = object_string(entry, "message", "");
        actions = parse_ntfy_action_specs(entry);
        priority = (gint)object_number(entry, "priority", 0.0);
        message_time = (gint64)object_number(entry, "time", 0.0);
        if (message_time > newest_time) {
            newest_time = message_time;
        }
        ntfy_mark_seen(message_id);
        if (!initial_sync) {
            if (hide_content) {
                display_title = g_strdup("New ntfy notification");
                display_message = g_strdup((topic != NULL && *topic != '\0') ? "Content hidden for privacy." : "Content hidden.");
                if (actions != NULL) {
                    g_ptr_array_set_size(actions, 0);
                }
            } else {
                display_title = g_strdup((title != NULL && *title != '\0') ? title : ((topic != NULL && *topic != '\0') ? topic : "ntfy"));
                display_message = g_strdup(message);
            }
            notify_desktop_ntfy(display_title, display_message, topic, priority, actions);
        }
        g_free(event);
        g_free(message_id);
        g_free(topic);
        g_free(title);
        g_free(message);
        g_free(display_title);
        g_free(display_message);
        if (actions != NULL) {
            g_ptr_array_free(actions, TRUE);
        }
    }
    g_strfreev(lines);

    g_service.ntfy_since_time = newest_time > 0 ? newest_time : (g_get_real_time() / G_USEC_PER_SEC);
    g_service.ntfy_cursor_ready = TRUE;
    ok = TRUE;

    g_free(topics_path);
    g_free(auth_header);
    g_free(url);
    g_free(payload);
    g_clear_error(&error);

cleanup:
    g_free(settings);
    g_free(ntfy_obj);
    g_free(server_url);
    g_free(token);
    g_free(username);
    g_free(password);
    g_free(auth_mode);
    g_free(legacy_topic);
    if (selected_topics != NULL) {
        g_ptr_array_free(selected_topics, TRUE);
    }
    if (effective_topics != NULL) {
        g_ptr_array_free(effective_topics, TRUE);
    }
    return ok;
}

static GPtrArray *parse_plugin_tasks_manifest(const gchar *manifest_path, const gchar *plugin_dir) {
    gchar *text = load_file_text(manifest_path);
    gchar *tasks_json = extract_array_block(text, "tasks");
    gchar *plugin_id = object_string(text, "plugin_id", "");
    GPtrArray *tasks = g_ptr_array_new_with_free_func(plugin_task_spec_free);
    const gchar *cursor = tasks_json;
    gchar *plugin_name = g_path_get_basename(plugin_dir);

    if (plugin_id == NULL || *plugin_id == '\0') {
        g_free(plugin_id);
        plugin_id = g_strdup(plugin_name);
    }

    if (tasks_json == NULL) {
        goto cleanup;
    }

    while ((cursor = strchr(cursor, '{')) != NULL) {
        gint depth = 0;
        gboolean in_string = FALSE;
        gboolean escaped = FALSE;
        const gchar *end = NULL;
        gchar *task_json = NULL;
        PluginTaskSpec *task = NULL;

        for (const gchar *scan = cursor; *scan != '\0'; ++scan) {
            const gchar ch = *scan;
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

        task_json = g_strndup(cursor, (gsize)(end - cursor + 1));
        task = g_new0(PluginTaskSpec, 1);
        task->plugin_id = g_strdup(plugin_id);
        task->plugin_dir = g_strdup(plugin_dir);
        task->task_id = object_string(task_json, "id", "");
        task->interval_seconds = (gint)object_number(task_json, "interval_seconds", 300.0);
        task->timeout_seconds = (gint)object_number(task_json, "timeout_seconds", 25.0);
        task->working_dir = object_string(task_json, "working_dir", "");
        task->command = object_string_array(task_json, "command");
        if (task->interval_seconds < 20) {
            task->interval_seconds = 20;
        }
        if (task->timeout_seconds < 3) {
            task->timeout_seconds = 3;
        }
        gboolean enabled = object_bool(task_json, "enabled", TRUE);

        if (!enabled || task->task_id == NULL || *task->task_id == '\0' || task->command == NULL || task->command->len == 0) {
            plugin_task_spec_free(task);
        } else {
            for (guint i = 0; i < task->command->len; ++i) {
                gchar *arg = g_ptr_array_index(task->command, i);
                gchar *expanded = expand_plugin_token_string(arg, plugin_dir);
                g_free(arg);
                g_ptr_array_index(task->command, i) = expanded;
            }
            gchar *expanded_workdir = expand_plugin_token_string(task->working_dir, plugin_dir);
            g_free(task->working_dir);
            task->working_dir = expanded_workdir;
            g_ptr_array_add(tasks, task);
        }

        g_free(task_json);
        cursor = end + 1;
    }

cleanup:
    g_free(text);
    g_free(tasks_json);
    g_free(plugin_id);
    g_free(plugin_name);
    return tasks;
}

static gboolean run_plugin_task(PluginTaskSpec *task) {
    GSubprocessLauncher *launcher = NULL;
    GSubprocess *process = NULL;
    GError *error = NULL;
    gboolean ok = FALSE;
    gchar **argv = NULL;
    if (task == NULL || task->command == NULL || task->command->len == 0) {
        return FALSE;
    }

    argv = g_new0(gchar *, task->command->len + 1);
    for (guint i = 0; i < task->command->len; ++i) {
        argv[i] = g_strdup(g_ptr_array_index(task->command, i));
    }
    argv[task->command->len] = NULL;

    launcher = g_subprocess_launcher_new(G_SUBPROCESS_FLAGS_STDOUT_SILENCE | G_SUBPROCESS_FLAGS_STDERR_SILENCE);
    g_subprocess_launcher_setenv(launcher, "HANAUTA_SETTINGS_PATH", g_service.settings_path, TRUE);
    g_subprocess_launcher_setenv(launcher, "HANAUTA_STATE_DIR", g_service.state_dir, TRUE);
    g_subprocess_launcher_setenv(launcher, "HANAUTA_SERVICE_STATE_DIR", g_service.state_dir, TRUE);
    if (task->plugin_id != NULL && *task->plugin_id != '\0') {
        g_subprocess_launcher_setenv(launcher, "HANAUTA_PLUGIN_ID", task->plugin_id, TRUE);
    }
    if (task->plugin_dir != NULL && *task->plugin_dir != '\0') {
        g_subprocess_launcher_setenv(launcher, "HANAUTA_PLUGIN_DIR", task->plugin_dir, TRUE);
    }
    if (task->working_dir != NULL && *task->working_dir != '\0' && g_file_test(task->working_dir, G_FILE_TEST_IS_DIR)) {
        g_subprocess_launcher_set_cwd(launcher, task->working_dir);
    }
    process = g_subprocess_launcher_spawnv(launcher, (const gchar * const *)argv, &error);
    if (process == NULL) {
        g_clear_error(&error);
        goto cleanup;
    }
    if (!g_subprocess_wait(process, NULL, &error)) {
        g_clear_error(&error);
        goto cleanup;
    }
    if (!g_subprocess_get_successful(process)) {
        goto cleanup;
    }
    ok = TRUE;

cleanup:
    if (argv != NULL) {
        g_strfreev(argv);
    }
    g_clear_object(&process);
    g_clear_object(&launcher);
    g_clear_error(&error);
    return ok;
}

static void refresh_plugin_background_tasks(void) {
    GPtrArray *plugin_dirs = collect_plugin_dirs();
    gint64 now = g_get_real_time() / G_USEC_PER_SEC;
    for (guint i = 0; i < plugin_dirs->len; ++i) {
        const gchar *plugin_dir = g_ptr_array_index(plugin_dirs, i);
        gchar *manifest_path = g_build_filename(plugin_dir, "hanauta-service-plugin.json", NULL);
        GPtrArray *tasks = NULL;
        if (!g_file_test(manifest_path, G_FILE_TEST_EXISTS)) {
            g_free(manifest_path);
            continue;
        }
        tasks = parse_plugin_tasks_manifest(manifest_path, plugin_dir);
        g_free(manifest_path);
        for (guint j = 0; j < tasks->len; ++j) {
            PluginTaskSpec *task = g_ptr_array_index(tasks, j);
            gchar *task_key = g_strdup_printf("%s::%s", task->plugin_id, task->task_id);
            gpointer slot = g_hash_table_lookup(g_service.plugin_task_next_run, task_key);
            gint64 due_at = slot != NULL ? GPOINTER_TO_INT(slot) : 0;
            gboolean should_run = due_at <= 0 || now >= due_at;
            if (should_run) {
                gboolean ok = run_plugin_task(task);
                gint next_interval = ok ? task->interval_seconds : MIN(task->interval_seconds, 60);
                if (next_interval < 10) {
                    next_interval = 10;
                }
                g_hash_table_replace(g_service.plugin_task_next_run, task_key, GINT_TO_POINTER((gint)(now + next_interval)));
            } else {
                g_free(task_key);
            }
        }
        g_ptr_array_free(tasks, TRUE);
    }
    g_ptr_array_free(plugin_dirs, TRUE);
}

static gboolean refresh_all(gpointer user_data) {
    (void)user_data;
    gboolean wifi_ok = refresh_wifi();
    gboolean weather_ok = refresh_weather();
    gboolean crypto_ok = refresh_crypto();
    gboolean home_assistant_ok = refresh_home_assistant();
    gboolean ntfy_ok = refresh_ntfy();
    refresh_plugin_background_tasks();
    gboolean any_ok = wifi_ok || weather_ok || crypto_ok || home_assistant_ok || ntfy_ok;
    write_status_json(
        any_ok ? "running" : "idle",
        any_ok ? "Background caches refreshed." : "Waiting for enabled services."
    );
    return G_SOURCE_CONTINUE;
}

static gboolean write_heartbeat(gpointer user_data) {
    (void)user_data;
    write_status_json("running", "Service heartbeat updated.");
    return G_SOURCE_CONTINUE;
}

static void settings_changed(
    GFileMonitor *monitor,
    GFile *file,
    GFile *other_file,
    GFileMonitorEvent event_type,
    gpointer user_data
) {
    (void)monitor;
    (void)file;
    (void)other_file;
    (void)user_data;
    if (event_type == G_FILE_MONITOR_EVENT_CHANGES_DONE_HINT || event_type == G_FILE_MONITOR_EVENT_CREATED) {
        refresh_all(NULL);
    }
}

int main(void) {
    GMainLoop *loop = NULL;
    GFile *settings_file = NULL;
    GError *error = NULL;

    g_service.settings_path = g_build_filename(g_get_home_dir(), ".local", "state", "hanauta", "notification-center", "settings.json", NULL);
    g_service.state_dir = g_build_filename(g_get_home_dir(), ".local", "state", "hanauta", "service", NULL);
    g_service.weather_path = g_build_filename(g_service.state_dir, "weather.json", NULL);
    g_service.crypto_path = g_build_filename(g_service.state_dir, "crypto.json", NULL);
    g_service.wifi_path = g_build_filename(g_service.state_dir, "wifi.json", NULL);
    g_service.home_assistant_path = g_build_filename(g_service.state_dir, "home_assistant.json", NULL);
    g_service.status_path = g_build_filename(g_service.state_dir, "status.json", NULL);
    g_service.ntfy_all_topics_cache = g_ptr_array_new_with_free_func(g_free);
    g_service.ntfy_seen_ids = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);
    g_service.plugin_task_next_run = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);

    g_mkdir_with_parents(g_service.state_dir, 0755);
    write_status_json("starting", "Initializing service caches.");

    settings_file = g_file_new_for_path(g_service.settings_path);
    g_service.settings_monitor = g_file_monitor_file(settings_file, G_FILE_MONITOR_NONE, NULL, &error);
    if (g_service.settings_monitor != NULL) {
        g_signal_connect(g_service.settings_monitor, "changed", G_CALLBACK(settings_changed), NULL);
    } else {
        g_clear_error(&error);
    }

    refresh_all(NULL);
    g_service.heartbeat_source = g_timeout_add_seconds(60, write_heartbeat, NULL);
    g_service.refresh_source = g_timeout_add_seconds(5, refresh_all, NULL);

    loop = g_main_loop_new(NULL, FALSE);
    g_main_loop_run(loop);

    if (g_service.refresh_source != 0) {
        g_source_remove(g_service.refresh_source);
    }
    if (g_service.heartbeat_source != 0) {
        g_source_remove(g_service.heartbeat_source);
    }
    g_clear_object(&g_service.settings_monitor);
    g_clear_object(&settings_file);
    g_main_loop_unref(loop);
    g_free(g_service.settings_path);
    g_free(g_service.state_dir);
    g_free(g_service.weather_path);
    g_free(g_service.crypto_path);
    g_free(g_service.wifi_path);
    g_free(g_service.home_assistant_path);
    g_free(g_service.status_path);
    g_free(g_service.ntfy_topic_key);
    if (g_service.ntfy_all_topics_cache != NULL) {
        g_ptr_array_free(g_service.ntfy_all_topics_cache, TRUE);
    }
    if (g_service.ntfy_seen_ids != NULL) {
        g_hash_table_unref(g_service.ntfy_seen_ids);
    }
    if (g_service.plugin_task_next_run != NULL) {
        g_hash_table_unref(g_service.plugin_task_next_run);
    }
    return 0;
}
