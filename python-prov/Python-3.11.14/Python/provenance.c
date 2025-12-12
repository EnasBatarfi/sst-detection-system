#include "Python.h"
#include "provenance.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <ctype.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

#define PROV_TABLE_SIZE 65536

/* ===== Thread-local current owner support (internal) ===== */

static __thread char current_owner[128] = "";
static char _pv_last_primary_owner[128] = "";

/* Internal: set current owner from C (we'll call this from TagOwned) */
static void
_PyProv_SetCurrentOwnerInternal(const char *owner)
{
    if (!owner || !*owner) {
        current_owner[0] = '\0';
        return;
    }
    strncpy(current_owner, owner, sizeof(current_owner) - 1);
    current_owner[sizeof(current_owner) - 1] = '\0';
}

/* Public (to other C files) getter */
const char *
_PyProv_GetCurrentOwner(void)
{
    return current_owner[0] ? current_owner : NULL;
}

typedef struct {
    void *key;
    int tag;            /* 0 = no, 1 = sensitive */
    char owner[128];    /* short owner string, e.g. email */
} ProvEntry;

static ProvEntry prov_table[PROV_TABLE_SIZE];


static inline uint64_t hash_ptr(void *p) {
    uintptr_t x = (uintptr_t)p;
    x ^= x >> 33;
    x *= 0xff51afd7ed558ccdULL;
    x ^= x >> 33;
    return x & (PROV_TABLE_SIZE - 1);
}

static ProvEntry *lookup(PyObject *key, int create) {
    if (!key) return NULL;
    size_t idx = (size_t)hash_ptr(key);
    for (size_t i = 0; i < PROV_TABLE_SIZE; i++) {
        size_t j = (idx + i) & (PROV_TABLE_SIZE - 1);
        if (prov_table[j].key == key) {
            return &prov_table[j];
        }
        if (!prov_table[j].key && create) {
            prov_table[j].key = (void *) key;
            prov_table[j].tag = 0;
            prov_table[j].owner[0] = '\0';
            return &prov_table[j];
        }
    }
    return NULL;
}

/* Basic tagging */

PyAPI_FUNC(void) _PyProv_Tag(PyObject *obj) {
    if (!obj) return;
    /* Delegate to TagOwned so it can reuse current_owner logic */
    _PyProv_TagOwned(obj, NULL);
}


static int
_pv_is_plausible_email(const char *s) {
    if (!s || !*s) {
        return 0;
    }
    const char *at  = strchr(s, '@');
    if (!at || at == s) {
        return 0;
    }
    const char *dot = strchr(at + 1, '.');
    if (!dot || dot[1] == '\0') {
        return 0;
    }
    /* Filter out obvious junk you have seen */
    if (strcmp(s, "<unknown>") == 0) return 0;
    if (strcmp(s, "@:") == 0) return 0;
    return 1;
}

/* Heuristic: require the payload to be mostly printable ASCII/whitespace. */
static int
_pv_is_mostly_printable(const char *s, Py_ssize_t len) {
    if (!s || len <= 0) {
        return 0;
    }
    Py_ssize_t printable = 0;
    for (Py_ssize_t i = 0; i < len; i++) {
        unsigned char c = (unsigned char)s[i];
        if (c == '\n' || c == '\r' || c == '\t' || (c >= 0x20 && c < 0x7f)) {
            printable++;
        }
    }
    return printable * 10 >= len * 7; /* >=70% printable */
}

PyAPI_FUNC(void) _PyProv_TagOwned(PyObject *obj, const char *owner) {
    if (!obj) {
        return;
    }

    /* Resolve owner: explicit or thread-local */
    const char *effective_owner = owner;
    if (!effective_owner || !*effective_owner) {
        const char *cur = _PyProv_GetCurrentOwner();
        if (cur && *cur) {
            effective_owner = cur;
        } else {
            /* No identity, do not tag at all */
            return;
        }
    }

    /* Require a plausible email, otherwise skip tagging */
    if (!_pv_is_plausible_email(effective_owner)) {
        return;
    }

    ProvEntry *e = lookup(obj, 1);
    if (!e) {
        return;
    }

    e->tag = 1;
    strncpy(e->owner, effective_owner, sizeof(e->owner) - 1);
    e->owner[sizeof(e->owner) - 1] = '\0';

    /* Also set thread-local current owner */
    _PyProv_SetCurrentOwnerInternal(effective_owner);
}


/* Query */

PyAPI_FUNC(ProvTag) _PyProv_Get(PyObject *obj) {
    if (!obj) return 0;
    ProvEntry *e = lookup(obj, 0);
    return (e && e->tag) ? 1 : 0;
}

PyAPI_FUNC(const char *) _PyProv_GetOwner(PyObject *obj) {
    if (!obj) {
        return NULL;
    }
    ProvEntry *e = lookup(obj, 0);
    if (!e || !e->tag || e->owner[0] == '\0') {
        return NULL;
    }
    return e->owner;
}

PyAPI_FUNC(void) _PyProv_ClearObject(PyObject *obj) {
    if (!obj) {
        return;
    }
    ProvEntry *e = lookup(obj, 0);
    if (!e) {
        return;
    }
    /* Do NOT clear e->key (that breaks open addressing).
       Just reset tag and owner so this pointer is considered clean
       if memory is reused for a new object. */
    e->tag = 0;
    e->owner[0] = '\0';
}
/* Propagation */

PyAPI_FUNC(void) _PyProv_Propagate(PyObject *result, PyObject *a, PyObject *b) {
    if (!result) return;
    if (_PyProv_Get(result)) return;

    ProvEntry *ea = a ? lookup(a, 0) : NULL;
    ProvEntry *eb = b ? lookup(b, 0) : NULL;

    const char *oa = (ea && ea->tag && ea->owner[0]) ? ea->owner : NULL;
    const char *ob = (eb && eb->tag && eb->owner[0]) ? eb->owner : NULL;

    char merged[256] = "";
    if (oa) strncat(merged, oa, sizeof(merged)-1);
    if (oa && ob) strncat(merged, ",", sizeof(merged)-1);
    if (ob) strncat(merged, ob, sizeof(merged)-1);

    const char *owner = merged[0] ? merged : NULL;


    if (!owner) {
        // Neither operand had provenance and no explicit owner.
        // Leave result untagged.
        return;
    }

    _PyProv_TagOwned(result, owner);

}


/* Sink logging */

static FILE *
_pv_log_stream(void)
{
    static int initialized = 0;
    static FILE *fp = NULL;

    if (!initialized) {
        const char *path = getenv("PY_PROVENANCE_LOG_JSON");
        if (path && *path) {
            fp = fopen(path, "a");
            if (!fp) {
                fp = stderr;
            }
        }
        else {
            fp = stderr;
        }
        initialized = 1;
    }
    return fp;
}

static void
_pv_write_json_string(FILE *fp, const char *s)
{
    fputc('"', fp);
    for (const unsigned char *p = (const unsigned char *)s; p && *p; p++) {
        switch (*p) {
        case '\\': fputs("\\\\", fp); break;
        case '"':  fputs("\\\"", fp); break;
        case '\n': fputs("\\n", fp);  break;
        case '\r': fputs("\\r", fp);  break;
        case '\t': fputs("\\t", fp);  break;
        default:
            if (*p < 0x20) {
                fprintf(fp, "\\u%04x", *p);
            }
            else {
                fputc(*p, fp);
            }
        }
    }
    fputc('"', fp);
}

static void
_pv_log_json_line(const char *sink, const char *owner_csv, const char *data_str, const char *dest)
{
    FILE *fp = _pv_log_stream();
    if (!fp) {
        return;
    }

    char ts[32];
    time_t now = time(NULL);
    struct tm tm_now;
    if (localtime_r(&now, &tm_now) != NULL) {
        strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", &tm_now);
    }
    else {
        strncpy(ts, "unknown", sizeof(ts) - 1);
        ts[sizeof(ts) - 1] = '\0';
    }

    static int source_init = 0;
    static char source_buf[128] = "";
    if (!source_init) {
        const char *env_src = getenv("PY_PROVENANCE_SOURCE");
        if (env_src && *env_src) {
            strncpy(source_buf, env_src, sizeof(source_buf) - 1);
            source_buf[sizeof(source_buf) - 1] = '\0';
        }
        else {
            int argc = 0;
            wchar_t **wargv = NULL;
            Py_GetArgcArgv(&argc, &wargv);
            const wchar_t *wpath = NULL;
            if (argc > 1 && wargv && wargv[1]) {
                wpath = wargv[1];
            }
            else if (argc > 0 && wargv && wargv[0]) {
                wpath = wargv[0];
            }
            if (argc > 0 && wargv && wargv[0]) {
                char *arg = Py_EncodeLocale(wpath ? wpath : wargv[0], NULL);
                if (arg) {
                    const char *base = strrchr(arg, '/');
#ifdef MS_WINDOWS
                    const char *bslash = strrchr(arg, '\\');
                    if (!base || (bslash && bslash > base)) base = bslash;
#endif
                    if (base && base[0]) {
                        base++;
                    }
                    else {
                        base = arg;
                    }
                    strncpy(source_buf, base, sizeof(source_buf) - 1);
                    source_buf[sizeof(source_buf) - 1] = '\0';
                    PyMem_Free(arg);
                }
            }
            if (source_buf[0] == '\0') {
                const wchar_t *wprog = Py_GetProgramName();
                if (wprog) {
                    char *prog = Py_EncodeLocale(wprog, NULL);
                    if (prog) {
                        strncpy(source_buf, prog, sizeof(source_buf) - 1);
                        source_buf[sizeof(source_buf) - 1] = '\0';
                        PyMem_Free(prog);
                    }
                }
            }
            if (source_buf[0] == '\0') {
                strncpy(source_buf, "provenance-runtime", sizeof(source_buf) - 1);
                source_buf[sizeof(source_buf) - 1] = '\0';
            }
        }
        source_init = 1;
    }

    /* Pretty, indented JSON block */
    fprintf(fp, "{\n");
    fprintf(fp, "  \"sink\": ");
    _pv_write_json_string(fp, sink ? sink : "<unknown>");
    fprintf(fp, ",\n  \"ts\": ");
    _pv_write_json_string(fp, ts);
    fprintf(fp, ",\n  \"source\": ");
    _pv_write_json_string(fp, source_buf);
    fprintf(fp, ",\n  \"pid\": %d", (int)getpid());
    if (dest && *dest) {
        fprintf(fp, ",\n  \"dest\": ");
        _pv_write_json_string(fp, dest);
    }
    fprintf(fp, ",\n  \"owners\": [\n");
    int first_owner = 1;
    if (owner_csv && *owner_csv) {
        const char *p = owner_csv;
        while (*p) {
            while (*p == ',' || isspace((unsigned char)*p)) {
                p++;
            }
            if (!*p) break;
            const char *start = p;
            while (*p && *p != ',') {
                p++;
            }
            size_t len = (size_t)(p - start);
            char buf[128];
            if (len >= sizeof(buf)) {
                len = sizeof(buf) - 1;
            }
            memcpy(buf, start, len);
            buf[len] = '\0';
            fprintf(fp, "    %s", first_owner ? "" : ",");
            _pv_write_json_string(fp, buf);
            fprintf(fp, "\n");
            first_owner = 0;
            if (*p == ',') p++;
        }
    }
    fprintf(fp, "  ],\n");
    fprintf(fp, "  \"data\": ");
    _pv_write_json_string(fp, data_str ? data_str : "<repr-error>");
    fprintf(fp, "\n}\n");
    fflush(fp);
}

/* Lightweight FNV-1a hash for deduping long payloads */
static uint64_t
_pv_hash64(const char *s)
{
    uint64_t h = 1469598103934665603ULL;
    if (!s) {
        return h;
    }
    for (const unsigned char *p = (const unsigned char *)s; *p; p++) {
        h ^= (uint64_t)(*p);
        h *= 1099511628211ULL;
    }
    return h;
}

/* Normalize owner CSV: keep plausible emails only, unique, rebuild CSV into out */
static int
_pv_normalize_owners(const char *owner_csv, char *out, size_t outsz)
{
    if (!owner_csv || !*owner_csv || !out || outsz == 0) {
        return 0;
    }

    size_t outlen = 0;
    int count = 0;
    const char *p = owner_csv;
    char seen[8][128];  /* small dedup list */
    int seen_count = 0;

    while (*p) {
        while (*p == ',' || isspace((unsigned char)*p)) {
            p++;
        }
        if (!*p) {
            break;
        }
        const char *start = p;
        while (*p && *p != ',') {
            p++;
        }
        size_t len = (size_t)(p - start);
        if (len >= sizeof(seen[0])) {
            len = sizeof(seen[0]) - 1;
        }
        char email[128];
        memcpy(email, start, len);
        email[len] = '\0';

        /* Trim whitespace and common wrappers like quotes/angle brackets */
        char *trimmed = email;
        while (*trimmed == ' ' || *trimmed == '\t' ||
               *trimmed == '<' || *trimmed == '"' || *trimmed == '\'') {
            trimmed++;
        }
        char *end = trimmed + strlen(trimmed);
        while (end > trimmed &&
               (end[-1] == ' ' || end[-1] == '\t' ||
                end[-1] == '>' || end[-1] == '"' || end[-1] == '\'' || end[-1] == ',')) {
            end--;
        }
        *end = '\0';
        if (trimmed != email) {
            memmove(email, trimmed, strlen(trimmed) + 1);
        }

        if (!_pv_is_plausible_email(email)) {
            if (*p == ',') p++;
            continue;
        }
        int dup = 0;
        for (int i = 0; i < seen_count; i++) {
            if (strcmp(seen[i], email) == 0) {
                dup = 1;
                break;
            }
        }
        if (dup) {
            if (*p == ',') p++;
            continue;
        }
        if (seen_count < (int)(sizeof(seen) / sizeof(seen[0]))) {
            strcpy(seen[seen_count++], email);
        }

        size_t need = len + (outlen ? 1 : 0);
        if (outlen + need + 1 >= outsz) {
            break;
        }
        if (outlen && out[outlen - 1] != ',') {
            out[outlen++] = ',';
        }
        memcpy(out + outlen, email, len);
        outlen += len;
        out[outlen] = '\0';
        count++;
        if (*p == ',') {
            p++;
        }
    }
    if (count == 0 && outsz > 0) {
        out[0] = '\0';
    }
    return count;
}

PyAPI_FUNC(void) _PyProv_LogIfSensitive(const char *sink, PyObject *obj, const char *dest) {
    if (!Py_IsInitialized() || PyErr_Occurred()) {
        return;
    }

    if (!obj) {
        return;
    }

    /* Ignore trivial writes (single char or only whitespace) for str/bytes */
    const char *trivial_buf = NULL;
    Py_ssize_t trivial_len = 0;

    if (PyUnicode_Check(obj)) {
        trivial_buf = PyUnicode_AsUTF8AndSize(obj, &trivial_len);
    } else if (PyBytes_Check(obj)) {
        trivial_buf = PyBytes_AS_STRING(obj);
        trivial_len = PyBytes_GET_SIZE(obj);
    } else if (PyByteArray_Check(obj)) {
        trivial_buf = PyByteArray_AS_STRING(obj);
        trivial_len = PyByteArray_GET_SIZE(obj);
    }

    if (trivial_buf && trivial_len > 0) {
        if (trivial_len <= 1 ||
            strspn(trivial_buf, " \n\r\t") == (size_t)trivial_len) {
            return;
        }
    }

    int tag = _PyProv_Get(obj);
    int table_tag = tag;   /* track whether provenance came from the object itself */
    const char *owner = NULL;
    int sensitive = 0;     /* true once any sensitive signal is found */

    /* If object is tagged in our table, use that owner */
    if (tag) {
        owner = _PyProv_GetOwner(obj);
        if (owner) sensitive = 1;
    }

    /* Fallback: inspect the actual string/bytes and extract ALL emails */
    char merged[512];
    merged[0] = '\0';

    if (!tag) {
        const char *s = NULL;
        Py_ssize_t size = 0;

        if (PyUnicode_Check(obj)) {
            s = PyUnicode_AsUTF8AndSize(obj, &size);
        } else if (PyBytes_Check(obj)) {
            s = PyBytes_AS_STRING(obj);
            size = PyBytes_GET_SIZE(obj);
        } else if (PyByteArray_Check(obj)) {
            s = PyByteArray_AS_STRING(obj);
            size = PyByteArray_GET_SIZE(obj);
        }

        if (s && size > 0) {
            const char *p = s;
            const char *end = s + size;

            while (p < end) {
                const char *at = memchr(p, '@', end - p);
                if (!at) {
                    break;
                }

                /* Expand left to email start */
                const char *start = at;
                while (start > s &&
                       start[-1] != ' ' &&
                       start[-1] != '\n' &&
                       start[-1] != '\t' &&
                       start[-1] != ',' &&
                       start[-1] != ':') {
                    start--;
                }

                /* Expand right to email end */
                const char *stop = at;
                while (stop < end &&
                       *stop != ' ' &&
                       *stop != '\n' &&
                       *stop != '\t' &&
                       *stop != ',' &&
                       *stop != '>') {
                    stop++;
                }

                char email[128];
                size_t elen = (size_t)(stop - start);
                if (elen >= sizeof(email)) {
                    elen = sizeof(email) - 1;
                }
                memcpy(email, start, elen);
                email[elen] = '\0';

                if (_pv_is_plausible_email(email)) {
                    if (merged[0] != '\0') {
                        strncat(merged, ",",
                                sizeof(merged) - strlen(merged) - 1);
                    }
                    strncat(merged, email,
                            sizeof(merged) - strlen(merged) - 1);
                }

                p = stop;
            }

            if (merged[0] != '\0') {
                owner = merged;
                tag = 1;          /* treat as sensitive */
                sensitive = 1;
            }
        }
    }

    /* Build readable data representation */
    PyObject *repr = NULL;
    const char *raw_buf = NULL;
    Py_ssize_t raw_len = 0;
    if (PyBytes_Check(obj)) {
        raw_buf = PyBytes_AS_STRING(obj);
        raw_len = PyBytes_GET_SIZE(obj);
        repr = PyUnicode_DecodeUTF8(PyBytes_AS_STRING(obj),
                                    PyBytes_Size(obj),
                                    "replace");
    }
    if (!repr) {
        repr = PyObject_Str(obj);
        if (repr && PyUnicode_Check(repr)) {
            raw_buf = PyUnicode_AsUTF8AndSize(repr, &raw_len);
        }
    }
    const char *data_str = NULL;
    if (repr && PyUnicode_Check(repr)) {
        data_str = PyUnicode_AsUTF8(repr);
    }
    if (!data_str) {
        data_str = "<repr-error>";
    }

    /* Late owner fallback: after we have the payload, allow thread owner for file/socket
       when there is some signal (tag, email, or nontrivial content such as digits). */
    if ((!tag || !owner) &&
        sink &&
        (strcmp(sink, "file_write") == 0 || strcmp(sink, "socket_send") == 0)) {
        int has_email = (data_str && strchr(data_str, '@') != NULL);
        int has_digit = 0;
        if (data_str) {
            for (const char *p = data_str; *p; p++) {
                if (isdigit((unsigned char)*p)) {
                    has_digit = 1;
                    break;
                }
            }
        }
        if (table_tag || has_email || has_digit) {
            const char *cur = _PyProv_GetCurrentOwner();
            if (cur && _pv_is_plausible_email(cur)) {
                owner = cur;
                tag = 1;
                sensitive = 1;
            }
        }
    }

    /* Thread-local fallback: only attach current owner when this object (or its
       parents) was actually provenance-tagged. Avoid tainting unrelated clean data. */
    if ((!tag || !owner) && table_tag) {
        const char *cur_owner = _PyProv_GetCurrentOwner();
        if (cur_owner && _pv_is_plausible_email(cur_owner)) {
            owner = cur_owner;
            tag = 1;
            sensitive = 1;
        }
    }

    /* If still not sensitive, bail out: treat as clean */
    if (!tag || !owner || !sensitive) {
        Py_XDECREF(repr);
        return;  // do not log, no provenance
    }

    /* For socket sends, trim verbose HTTP payloads to the first line only
       and skip obvious framework traffic (HTTP status lines, HTML/CSS). */
    char socket_trim[512];
    if (sink && strcmp(sink, "socket_send") == 0 && data_str) {
        if (strncmp(data_str, "HTTP/1.", 7) == 0 ||
            strncmp(data_str, "<!DOCTYPE", 9) == 0 ||
            strncmp(data_str, "/*", 2) == 0) {
            Py_XDECREF(repr);
            return;
        }
        const char *nl = strpbrk(data_str, "\r\n");
        if (nl) {
            size_t len = (size_t)(nl - data_str);
            if (len >= sizeof(socket_trim)) {
                len = sizeof(socket_trim) - 1;
            }
            memcpy(socket_trim, data_str, len);
            socket_trim[len] = '\0';
            data_str = socket_trim;
        }
    }

    /* Default log data is the full payload. */
    const char *log_data = data_str;

    /* For stdout/stderr: if we extracted emails into merged, only log that list.
       This collapses things like "Alice email: alice@example.com" into
       just "alice@example.com" and lets dedup kill redundant formatted prints. */
    if (sink && (strcmp(sink, "stdout") == 0 || strcmp(sink, "stderr") == 0)) {
        if (merged[0] != '\0') {
            log_data = merged;  /* e.g. "alice@example.com" or "alice@example.com,bob@example.com" */
        }
    }


    /* For stdout/stderr: drop if no tag/email/owner-derived signal survived. */
    if (sink && (strcmp(sink, "stdout") == 0 || strcmp(sink, "stderr") == 0)) {
        int has_email = (log_data && strchr(log_data, '@') != NULL);
        if (!table_tag && !has_email && merged[0] == '\0' && !sensitive) {
            Py_XDECREF(repr);
            return;
        }
    }

    char normalized[256];
    int owner_count = 0;

    /* Skip clearly binary junk to avoid false positives, except for socket_send where
       HTTPS/TLS records are binary but still worth logging when we have an owner. */
    if (raw_buf && raw_len > 0 && !_pv_is_mostly_printable(raw_buf, raw_len)) {
        if (!(sink && strcmp(sink, "socket_send") == 0 && owner)) {
            Py_XDECREF(repr);
            return;
        }
    }

    /* Skip file_write events that are trivial/clean or from in-memory buffers. */
    if (sink && strcmp(sink, "file_write") == 0) {
        if (!dest || !*dest) {
            Py_XDECREF(repr);
            return;
        }
        int has_email = (log_data && strchr(log_data, '@') != NULL);
        int has_digit = 0;
        if (log_data) {
            for (const char *p = log_data; *p; p++) {
                if (isdigit((unsigned char)*p)) {
                    has_digit = 1;
                    break;
                }
            }
        }
        if (!owner) {
            const char *cur = _PyProv_GetCurrentOwner();
            if (cur && _pv_is_plausible_email(cur)) {
                owner = cur;
                tag = 1;
                sensitive = 1;
                owner_count = _pv_normalize_owners(owner, normalized, sizeof(normalized));
                if (owner_count == 0) {
                    Py_XDECREF(repr);
                    return;
                }
            }
            /* If TLS owner was cleared, try the last primary owner we observed. */
            if ((!owner || !tag) &&
                _pv_last_primary_owner[0]) {
                owner = _pv_last_primary_owner;
                tag = 1;
                sensitive = 1;
                owner_count = _pv_normalize_owners(owner, normalized, sizeof(normalized));
                if (owner_count == 0) {
                    Py_XDECREF(repr);
                    return;
                }
            }
        }
        if (log_data && *log_data) {
            const char *trim = log_data;
            while (*trim && isspace((unsigned char)*trim))
                trim++;
            if (*trim == '\0') {
                Py_XDECREF(repr);
                return;
            }
            if (!has_email && !has_digit && !table_tag && merged[0] == '\0') {
                Py_XDECREF(repr);
                return;
            }
        }
    }

    owner_count = _pv_normalize_owners(owner, normalized, sizeof(normalized));
    if (owner_count == 0) {
        Py_XDECREF(repr);
        return;
    }

    /* Remember the primary owner so later sinks (like scoring) inherit it. */
    if (normalized[0]) {
        char primary[128];
        const char *comma = strchr(normalized, ',');
        size_t copy_len = comma ? (size_t)(comma - normalized) : strlen(normalized);
        if (copy_len >= sizeof(primary)) copy_len = sizeof(primary) - 1;
        memcpy(primary, normalized, copy_len);
        primary[copy_len] = '\0';
        _PyProv_SetCurrentOwnerInternal(primary);
        strncpy(_pv_last_primary_owner, primary, sizeof(_pv_last_primary_owner) - 1);
        _pv_last_primary_owner[sizeof(_pv_last_primary_owner) - 1] = '\0';
    }


    /* Skip duplicate consecutive messages to reduce noise.
       Treat stdout/stderr/file_write as one logical console group. */
    static char last_sink[64] = "";
    static char last_owner[256] = "";
    static char last_data[256] = "";
    static size_t last_data_len = 0;
    static uint64_t last_data_hash = 0;
    static char last_dest[256] = "";
    static uint64_t last_sig = 0;
    static int last_group = 0; /* 0 = none, 1 = console, 2 = other */
    int group = 2;
    const char *dedup_sink = sink;
    if (sink && (strcmp(sink, "stdout") == 0 ||
                 strcmp(sink, "stderr") == 0 ||
                 strcmp(sink, "file_write") == 0)) {
        group = 1;
        dedup_sink = "console";
    }
    int file_like = (sink && (strcmp(sink, "stdout") == 0 ||
                              strcmp(sink, "stderr") == 0 ||
                              strcmp(sink, "file_write") == 0));
    int dest_match = 0;
        /* Special handling for file_write: drop "superset" writes that only add
       non-sensitive suffix (no digits, no '@') on top of the last payload
       for the same file and owner. This avoids logging "999\nclean line" and
       "user age999user age" when we already logged the sensitive part. */

    if (dest && last_dest[0]) {
        dest_match = strcmp(last_dest, dest) == 0;
    } else if (!dest) {
        /* For file writes and console group, treat missing dest as same event */
        dest_match = file_like || !last_dest[0];
    }

        if (sink && strcmp(sink, "file_write") == 0 &&
        dest && *dest &&
        last_dest[0] && strcmp(last_dest, dest) == 0 &&
        last_owner[0] && strcmp(last_owner, normalized) == 0 &&
        last_data[0] && log_data) {

        size_t prev_len = last_data_len;
        size_t cur_len = strlen(log_data);

        if (cur_len > prev_len &&
            strncmp(log_data, last_data, prev_len) == 0) {

            const char *suffix = log_data + prev_len;

            /* Skip leading whitespace in the suffix */
            while (*suffix && isspace((unsigned char)*suffix)) {
                suffix++;
            }

            int suffix_sensitive = 0;
            for (const char *p = suffix; *p; p++) {
                if (isdigit((unsigned char)*p) || *p == '@') {
                    suffix_sensitive = 1;
                    break;
                }
            }

            /* If the suffix is non-sensitive, ignore this aggregated write */
            if (!suffix_sensitive) {
                Py_XDECREF(repr);
                return;
            }
        }
    }


    size_t data_len = log_data ? strlen(log_data) : 0;
    uint64_t data_hash = _pv_hash64(log_data);
    uint64_t owner_hash = _pv_hash64(normalized);
    uint64_t dest_hash = _pv_hash64(dest ? dest : "");
    uint64_t sig = data_hash ^ (owner_hash << 1) ^ (dest_hash << 2);
    int data_same = 0;
    if (log_data) {
        if (data_len < sizeof(last_data) && last_data_len < sizeof(last_data)) {
            data_same = strcmp(last_data, log_data) == 0;
        } else {
            data_same = (last_data_len == data_len) && (last_data_hash == data_hash);
        }
    }

    if (last_sink[0] && last_owner[0] && last_data[0] &&
        dedup_sink && strcmp(last_sink, dedup_sink) == 0 &&
        strcmp(last_owner, normalized) == 0 &&
        data_same &&
        dest_match &&
        group == last_group &&
        sig == last_sig) {
        Py_XDECREF(repr);
        return;
    }

    /* Cache current message */
    if (dedup_sink) {
        strncpy(last_sink, dedup_sink, sizeof(last_sink) - 1);
        last_sink[sizeof(last_sink) - 1] = '\0';
    } else {
        last_sink[0] = '\0';
    }
    strncpy(last_owner, normalized, sizeof(last_owner) - 1);
    last_owner[sizeof(last_owner) - 1] = '\0';
    if (log_data) {
        strncpy(last_data, log_data, sizeof(last_data) - 1);
        last_data[sizeof(last_data) - 1] = '\0';
        last_data_len = data_len;
        last_data_hash = data_hash;
    } else {
        last_data[0] = '\0';
        last_data_len = 0;
        last_data_hash = 0;
    }
    if (dest && *dest) {
        strncpy(last_dest, dest, sizeof(last_dest) - 1);
        last_dest[sizeof(last_dest) - 1] = '\0';
    }
    else if (!(sink && strcmp(sink, "file_write") == 0)) {
        last_dest[0] = '\0';
    }
    last_group = group;
    last_sig = sig;

    _pv_log_json_line(sink ? sink : "<unknown>", normalized, log_data, dest);

    Py_XDECREF(repr);
}

/* Clear the thread-local current owner */
PyAPI_FUNC(void) _PyProv_ClearCurrentOwner(void) {
    current_owner[0] = '\0';
}
