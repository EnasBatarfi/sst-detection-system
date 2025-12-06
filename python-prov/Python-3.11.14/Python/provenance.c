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
            /* Ignore single chars and whitespace-only writes */
            if (size <= 1 || strspn(s, " \n\r\t") == (size_t)size) {
                return;
            }
        }
    }

    int tag = _PyProv_Get(obj);
    const char *owner = NULL;

    /* If object is tagged in our table, use that owner */
    if (tag) {
        owner = _PyProv_GetOwner(obj);
    }

    /* Fallback: inspect the actual string and extract ALL emails */
    char merged[512];
    merged[0] = '\0';

    if (!tag && PyUnicode_Check(obj)) {
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

                /* Expand left to email start */
                const char *start = at;
                while (start > s && start[-1] != ' ' && start[-1] != '\n' && start[-1] != '\t')
                    start--;

                /* Expand right to email end */
                const char *stop = at;
                while (stop < end && *stop != ' ' && *stop != '\n' && *stop != '\t')
                    stop++;

                /* Extract this email */
                char email[128];
                size_t len = (size_t)(stop - start);
                if (len >= sizeof(email)) {
                    len = sizeof(email) - 1;
                }
                memcpy(email, start, len);
                email[len] = '\0';

                /* Append to merged list */
                if (merged[0] != '\0') {
                    strncat(merged, ",", sizeof(merged) - strlen(merged) - 1);
                }
                strncat(merged, email, sizeof(merged) - strlen(merged) - 1);

                /* Continue scanning after this email */
                p = stop;
            }

            if (merged[0] != '\0') {
                owner = merged;
                tag = 1; /* treat as sensitive */
                
            }
        }
    }
    /* If still not sensitive, bail out: treat as clean */
    if (!tag || !owner) {
        return;  // do not log, no provenance
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
PyAPI_FUNC(void) _PyProv_ClearCurrentOwner(void) {
    current_owner[0] = '\0';
}
