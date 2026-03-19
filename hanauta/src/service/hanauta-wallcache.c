#include <glib.h>
#include <glib/gstdio.h>

#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

typedef struct {
    gchar *path;
    gchar *name;
    gchar *folder;
    gchar *thumb;
} WallpaperItem;

static gchar *build_path_from_home(const gchar *suffix) {
    return g_build_filename(g_get_home_dir(), suffix, NULL);
}

static gchar *settings_path(void) {
    return g_build_filename(
        g_get_home_dir(),
        ".local",
        "state",
        "hanauta",
        "notification-center",
        "settings.json",
        NULL
    );
}

static gchar *state_dir(void) {
    return g_build_filename(g_get_home_dir(), ".local", "state", "hanauta", "service", NULL);
}

static gchar *cache_path(void) {
    gchar *dir = state_dir();
    gchar *path = g_build_filename(dir, "wallpaper-index.json", NULL);
    g_free(dir);
    return path;
}

static gchar *thumb_cache_dir(void) {
    return g_build_filename(g_get_home_dir(), ".local", "state", "hanauta", "wallpaper-thumbs", NULL);
}

static gchar *escape_json_string(const gchar *text) {
    GString *out = g_string_new("");
    const guchar *cursor = (const guchar *)(text != NULL ? text : "");
    while (*cursor != '\0') {
        switch (*cursor) {
            case '\\':
                g_string_append(out, "\\\\");
                break;
            case '"':
                g_string_append(out, "\\\"");
                break;
            case '\n':
                g_string_append(out, "\\n");
                break;
            case '\r':
                g_string_append(out, "\\r");
                break;
            case '\t':
                g_string_append(out, "\\t");
                break;
            default:
                if (*cursor < 0x20) {
                    g_string_append_printf(out, "\\u%04x", *cursor);
                } else {
                    g_string_append_c(out, (gchar)*cursor);
                }
                break;
        }
        cursor++;
    }
    return g_string_free(out, FALSE);
}

static gchar *json_string_value(const gchar *json, const gchar *key) {
    gchar *pattern = g_strdup_printf("\"%s\"", key);
    const gchar *found = g_strstr_len(json, -1, pattern);
    const gchar *start = NULL;
    const gchar *end = NULL;
    gchar *value = NULL;

    g_free(pattern);
    if (found == NULL) {
        return NULL;
    }

    start = strchr(found, ':');
    if (start == NULL) {
        return NULL;
    }
    start++;
    while (*start == ' ' || *start == '\t' || *start == '\n' || *start == '\r') {
        start++;
    }
    if (*start != '"') {
        return NULL;
    }
    start++;
    end = start;
    while (*end != '\0' && *end != '"') {
        if (*end == '\\' && *(end + 1) != '\0') {
            end += 2;
        } else {
            end++;
        }
    }
    if (*end != '"') {
        return NULL;
    }
    value = g_strndup(start, (gsize)(end - start));
    return value;
}

static gboolean is_supported_image(const gchar *name) {
    if (name == NULL) {
        return FALSE;
    }
    return g_str_has_suffix(name, ".png")
        || g_str_has_suffix(name, ".jpg")
        || g_str_has_suffix(name, ".jpeg")
        || g_str_has_suffix(name, ".webp")
        || g_str_has_suffix(name, ".bmp")
        || g_str_has_suffix(name, ".PNG")
        || g_str_has_suffix(name, ".JPG")
        || g_str_has_suffix(name, ".JPEG")
        || g_str_has_suffix(name, ".WEBP")
        || g_str_has_suffix(name, ".BMP");
}

static gchar *display_name_for_path(const gchar *path) {
    gchar *basename = g_path_get_basename(path);
    gchar *dot = strrchr(basename, '.');
    gchar *cursor = basename;

    if (dot != NULL) {
        *dot = '\0';
    }
    while (*cursor != '\0') {
        if (*cursor == '_' || *cursor == '-') {
            *cursor = ' ';
        }
        cursor++;
    }
    g_strstrip(basename);
    if (*basename == '\0') {
        g_free(basename);
        return g_path_get_basename(path);
    }
    return basename;
}

static gchar *thumb_path_for_image(const gchar *path) {
    struct stat st;
    gchar *resolved = g_canonicalize_filename(path, NULL);
    gchar *payload = NULL;
    gchar *checksum = NULL;
    gchar *thumb_dir = NULL;
    gchar *thumb = NULL;
    long long mtime_ns = 0;

    if (resolved == NULL) {
        resolved = g_strdup(path);
    }
    if (g_stat(resolved, &st) != 0) {
        g_free(resolved);
        return g_strdup(path);
    }

    mtime_ns = (long long)st.st_mtime * 1000000000LL;

    payload = g_strdup_printf("%s|%lld|%lld", resolved, mtime_ns, (long long)st.st_size);
    checksum = g_compute_checksum_for_string(G_CHECKSUM_SHA1, payload, -1);
    thumb_dir = thumb_cache_dir();
    thumb = g_build_filename(thumb_dir, checksum, NULL);
    {
        gchar *with_ext = g_strconcat(thumb, ".jpg", NULL);
        g_free(thumb);
        thumb = with_ext;
    }

    g_free(thumb_dir);
    g_free(checksum);
    g_free(payload);
    g_free(resolved);

    if (g_file_test(thumb, G_FILE_TEST_EXISTS)) {
        return thumb;
    }
    g_free(thumb);
    return g_strdup(path);
}

static void wallpaper_item_free(gpointer data) {
    WallpaperItem *item = data;
    if (item == NULL) {
        return;
    }
    g_free(item->path);
    g_free(item->name);
    g_free(item->folder);
    g_free(item->thumb);
    g_free(item);
}

static gint wallpaper_item_compare(gconstpointer a, gconstpointer b) {
    const WallpaperItem *item_a = *(WallpaperItem * const *)a;
    const WallpaperItem *item_b = *(WallpaperItem * const *)b;
    return g_ascii_strcasecmp(item_a->path, item_b->path);
}

static GPtrArray *scan_folder_items(const gchar *root_folder) {
    GPtrArray *items = g_ptr_array_new_with_free_func(wallpaper_item_free);
    GQueue queue = G_QUEUE_INIT;

    if (!g_file_test(root_folder, G_FILE_TEST_IS_DIR)) {
        return items;
    }

    g_queue_push_tail(&queue, g_strdup(root_folder));

    while (!g_queue_is_empty(&queue)) {
        gchar *current_dir = g_queue_pop_head(&queue);
        GError *error = NULL;
        GDir *dir = g_dir_open(current_dir, 0, &error);

        if (dir == NULL) {
            g_clear_error(&error);
            g_free(current_dir);
            continue;
        }

        for (const gchar *name = g_dir_read_name(dir); name != NULL; name = g_dir_read_name(dir)) {
            gchar *child = g_build_filename(current_dir, name, NULL);
            if (g_file_test(child, G_FILE_TEST_IS_DIR)) {
                g_queue_push_tail(&queue, child);
                continue;
            }
            if (!g_file_test(child, G_FILE_TEST_IS_REGULAR) || !is_supported_image(name)) {
                g_free(child);
                continue;
            }

            WallpaperItem *item = g_new0(WallpaperItem, 1);
            gchar *parent_dir = g_path_get_dirname(child);
            item->path = child;
            item->name = display_name_for_path(child);
            item->thumb = thumb_path_for_image(child);
            item->folder = g_path_get_basename(parent_dir);
            g_free(parent_dir);
            g_ptr_array_add(items, item);
        }

        g_dir_close(dir);
        g_free(current_dir);
    }

    g_ptr_array_sort(items, wallpaper_item_compare);
    return items;
}

static void append_folder_json(GString *json, const gchar *folder_path, gboolean *first_folder) {
    GPtrArray *items = scan_folder_items(folder_path);
    gchar *folder_q = escape_json_string(folder_path);

    if (!*first_folder) {
        g_string_append(json, ",\n");
    }
    *first_folder = FALSE;

    g_string_append_printf(json, "    \"%s\": {\n", folder_q);
    g_string_append_printf(json, "      \"count\": %u,\n", items->len);
    g_string_append(json, "      \"items\": [\n");

    for (guint i = 0; i < items->len; i++) {
        WallpaperItem *item = g_ptr_array_index(items, i);
        gchar *path_q = escape_json_string(item->path);
        gchar *name_q = escape_json_string(item->name);
        gchar *folder_name_q = escape_json_string(item->folder);
        gchar *thumb_q = escape_json_string(item->thumb);

        g_string_append_printf(
            json,
            "        {\"path\": \"%s\", \"name\": \"%s\", \"folder\": \"%s\", \"thumb\": \"%s\"}%s\n",
            path_q,
            name_q,
            folder_name_q,
            thumb_q,
            (i + 1 < items->len) ? "," : ""
        );

        g_free(path_q);
        g_free(name_q);
        g_free(folder_name_q);
        g_free(thumb_q);
    }

    g_string_append(json, "      ]\n");
    g_string_append(json, "    }");

    g_free(folder_q);
    g_ptr_array_free(items, TRUE);
}

static GPtrArray *folders_to_scan(void) {
    GPtrArray *folders = g_ptr_array_new_with_free_func(g_free);
    GHashTable *seen = g_hash_table_new_full(g_str_hash, g_str_equal, g_free, NULL);
    gchar *settings = NULL;
    gchar *settings_file = settings_path();
    gchar *d3ext = build_path_from_home(".config/i3/hanauta/walls/D3Ext-aesthetic-wallpapers");
    gchar *jakoolit = build_path_from_home(".config/i3/hanauta/walls/JaKooLit-Wallpaper-Bank");

    if (g_file_test(d3ext, G_FILE_TEST_IS_DIR)) {
        g_hash_table_add(seen, g_strdup(d3ext));
        g_ptr_array_add(folders, g_strdup(d3ext));
    }
    if (g_file_test(jakoolit, G_FILE_TEST_IS_DIR) && !g_hash_table_contains(seen, jakoolit)) {
        g_hash_table_add(seen, g_strdup(jakoolit));
        g_ptr_array_add(folders, g_strdup(jakoolit));
    }

    if (g_file_get_contents(settings_file, &settings, NULL, NULL)) {
        gchar *provider = json_string_value(settings, "wallpaper_provider");
        gchar *folder = json_string_value(settings, "slideshow_folder");
        if (provider != NULL && folder != NULL && g_ascii_strcasecmp(provider, "konachan") != 0) {
            gchar *expanded = g_strdup(folder);
            if (g_str_has_prefix(expanded, "~")) {
                gchar *tmp = g_build_filename(g_get_home_dir(), expanded + 1, NULL);
                g_free(expanded);
                expanded = tmp;
            }
            if (g_file_test(expanded, G_FILE_TEST_IS_DIR) && !g_hash_table_contains(seen, expanded)) {
                g_hash_table_add(seen, g_strdup(expanded));
                g_ptr_array_add(folders, g_strdup(expanded));
            }
            g_free(expanded);
        }
        g_free(provider);
        g_free(folder);
    }

    g_free(settings);
    g_free(settings_file);
    g_free(d3ext);
    g_free(jakoolit);
    g_hash_table_destroy(seen);
    return folders;
}

static gboolean build_cache_for_folders(GPtrArray *folders, GError **error) {
    gchar *dir = state_dir();
    gchar *path = cache_path();
    GString *json = g_string_new("{\n");
    GDateTime *now = g_date_time_new_now_local();
    gchar *timestamp = g_date_time_format(now, "%Y-%m-%dT%H:%M:%S%z");
    gboolean first_folder = TRUE;
    gboolean ok = FALSE;

    g_mkdir_with_parents(dir, 0700);
    g_string_append_printf(json, "  \"generated_at\": \"%s\",\n", timestamp);
    g_string_append(json, "  \"folders\": {\n");

    for (guint i = 0; i < folders->len; i++) {
        const gchar *folder = g_ptr_array_index(folders, i);
        append_folder_json(json, folder, &first_folder);
    }

    g_string_append(json, "\n  }\n}\n");
    ok = g_file_set_contents(path, json->str, -1, error);

    g_free(timestamp);
    g_date_time_unref(now);
    g_string_free(json, TRUE);
    g_free(dir);
    g_free(path);
    return ok;
}

static gint run_once_for_folder(const gchar *folder) {
    GPtrArray *folders = folders_to_scan();
    GError *error = NULL;
    gboolean present = FALSE;
    gint status = 0;

    if (!g_file_test(folder, G_FILE_TEST_IS_DIR)) {
        g_ptr_array_free(folders, TRUE);
        return 1;
    }
    for (guint i = 0; i < folders->len; i++) {
        if (g_strcmp0(g_ptr_array_index(folders, i), folder) == 0) {
            present = TRUE;
            break;
        }
    }
    if (!present) {
        g_ptr_array_add(folders, g_strdup(folder));
    }
    if (!build_cache_for_folders(folders, &error)) {
        g_printerr("hanauta-wallcache: %s\n", error != NULL ? error->message : "failed to write cache");
        g_clear_error(&error);
        status = 2;
    }
    g_ptr_array_free(folders, TRUE);
    return status;
}

static gint run_all_once(void) {
    GPtrArray *folders = folders_to_scan();
    GError *error = NULL;
    gint status = 0;

    if (!build_cache_for_folders(folders, &error)) {
        g_printerr("hanauta-wallcache: %s\n", error != NULL ? error->message : "failed to write cache");
        g_clear_error(&error);
        status = 2;
    }
    g_ptr_array_free(folders, TRUE);
    return status;
}

int main(int argc, char **argv) {
    if (argc == 3 && g_strcmp0(argv[1], "--folder") == 0) {
        return run_once_for_folder(argv[2]);
    }
    if (argc == 2 && g_strcmp0(argv[1], "--once") == 0) {
        return run_all_once();
    }

    for (;;) {
        run_all_once();
        g_usleep(300 * G_USEC_PER_SEC);
    }
}
