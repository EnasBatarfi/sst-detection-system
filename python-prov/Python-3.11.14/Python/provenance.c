#include "Python.h"
#include "provenance.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>

#define PROV_TABLE_SIZE 65536

/* ===== Thread-local current owner support (internal) ===== */

static __thread char current_owner[128] = "";

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


PyAPI_FUNC(void) _PyProv_TagOwned(PyObject *obj, const char *owner) {
    if (!obj) return;
    ProvEntry *e = lookup(obj, 1);
    if (!e) return;

    /* If no explicit owner, try the current thread owner */
    const char *effective_owner = owner;
    if (!effective_owner || !*effective_owner) {
        const char *cur = _PyProv_GetCurrentOwner();
        if (cur && *cur) {
            effective_owner = cur;
        } else {
            effective_owner = "<unknown>";
        }
    }

    e->tag = 1;
    strncpy(e->owner, effective_owner, sizeof(e->owner) - 1);
    e->owner[sizeof(e->owner) - 1] = '\0';

    /* 👇 If this looks like a user identity (e.g. email), set it as current owner */
    if (strchr(effective_owner, '@')) {
        _PyProv_SetCurrentOwnerInternal(effective_owner);
    }

    // fprintf(stderr, "[DEBUG] Tagging obj=%p owner=%s\n", (void *)obj, e->owner);
}


/* Query */

PyAPI_FUNC(ProvTag) _PyProv_Get(PyObject *obj) {
    if (!obj) return 0;
    ProvEntry *e = lookup(obj, 0);
    return (e && e->tag) ? 1 : 0;
}

PyAPI_FUNC(const char *) _PyProv_GetOwner(PyObject *obj) {
    if (!obj) return "<unknown>";
    ProvEntry *e = lookup(obj, 0);
    if (!e || !e->tag || e->owner[0] == '\0') {
        return "<unknown>";
    }
    return e->owner;
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

PyAPI_FUNC(void) _PyProv_LogIfSensitive(const char *sink, PyObject *obj) {
    if (!Py_IsInitialized() || PyErr_Occurred()) {
        return;
    }

    if (!obj) {
        return;
    }

    /* Ignore trivial writes (single char or only whitespace) */
    if (PyUnicode_Check(obj)) {
        Py_ssize_t size;
        const char *s = PyUnicode_AsUTF8AndSize(obj, &size);

        if (s && size > 0) {
            if (size <= 1 || strspn(s, " \n\r\t") == (size_t)size) {
                return;
            }
        }
    }

    int tag = _PyProv_Get(obj);
    const char *owner = NULL;

    if (tag) {
        owner = _PyProv_GetOwner(obj);
        /* Treat obviously useless owners as "no owner" */
        if (!owner || !owner[0] ||
            strcmp(owner, "<unknown>") == 0 ||
            strcmp(owner, "@:") == 0) {
            tag = 0;
            owner = NULL;
        }
    }

    /* Always try to extract emails from the actual string content */
    char merged[512];
    merged[0] = '\0';

    if (PyUnicode_Check(obj)) {
        Py_ssize_t size;
        const char *s = PyUnicode_AsUTF8AndSize(obj, &size);
        if (s && size > 0) {
            const char *p = s;
            const char *end = s + size;

            while (p < end) {
                const char *at = memchr(p, '@', end - p);
                if (!at) {
                    break;
                }

                /* Expand left to (rough) email start, skipping punctuation */
                const char *start = at;
                while (start > s &&
                       start[-1] != ' ' && start[-1] != '\n' &&
                       start[-1] != '\t' && start[-1] != ',' &&
                       start[-1] != '\'' && start[-1] != '"') {
                    start--;
                }

                /* Expand right to (rough) email end, skipping punctuation */
                const char *stop = at;
                while (stop < end &&
                       *stop != ' ' && *stop != '\n' &&
                       *stop != '\t' && *stop != ',' &&
                       *stop != '\'' && *stop != '"') {
                    stop++;
                }

                char email[128];
                size_t len = (size_t)(stop - start);
                if (len >= sizeof(email)) {
                    len = sizeof(email) - 1;
                }
                memcpy(email, start, len);
                email[len] = '\0';

                if (merged[0] != '\0') {
                    strncat(merged, ",", sizeof(merged) - strlen(merged) - 1);
                }
                strncat(merged, email, sizeof(merged) - strlen(merged) - 1);

                p = stop;
            }
        }

        if (merged[0] != '\0') {
            /* Prefer email(s) found in the string over any previous junk */
            owner = merged;
            tag = 1;
        }
    }

    /* If still not sensitive, bail out: treat as clean */
    if (!tag || !owner) {
        return;
    }

    /* Build readable data representation */
    PyObject *repr = PyObject_Str(obj);
    const char *data_str = NULL;
    if (repr && PyUnicode_Check(repr)) {
        data_str = PyUnicode_AsUTF8(repr);
    }
    if (!data_str) {
        data_str = "<repr-error>";
    }

    fprintf(stderr, "[PROVENANCE] Sink=%s Owner=%s Data='%s'\n",
            sink, owner, data_str);

    Py_XDECREF(repr);
}
