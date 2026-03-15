#define _POSIX_C_SOURCE 200809L

#include <gio/gio.h>
#include <glib.h>
#include <stdbool.h>
#include <string.h>

typedef struct {
    gchar *settings_path;
    gchar *state_dir;
    gchar *weather_path;
    gchar *crypto_path;
    gchar *wifi_path;
    gchar *status_path;
    GFileMonitor *settings_monitor;
    guint heartbeat_source;
    guint refresh_source;
} HanautaService;

static HanautaService g_service = {0};

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
        "  \"wifi_cache\": \"service/wifi.json\"\n"
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

static gboolean refresh_all(gpointer user_data) {
    (void)user_data;
    gboolean wifi_ok = refresh_wifi();
    gboolean weather_ok = refresh_weather();
    gboolean crypto_ok = refresh_crypto();
    gboolean any_ok = wifi_ok || weather_ok || crypto_ok;
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
    g_service.status_path = g_build_filename(g_service.state_dir, "status.json", NULL);

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
    g_free(g_service.status_path);
    return 0;
}
