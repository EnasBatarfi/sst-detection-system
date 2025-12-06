#ifndef Py_PROVENANCE_H
#define Py_PROVENANCE_H

#include "Python.h"

typedef int ProvTag;

/* Basic tagging */
PyAPI_FUNC(void) _PyProv_Tag(PyObject *obj);
PyAPI_FUNC(void) _PyProv_TagOwned(PyObject *obj, const char *owner);

/* Query */
PyAPI_FUNC(ProvTag) _PyProv_Get(PyObject *obj);
PyAPI_FUNC(const char *) _PyProv_GetOwner(PyObject *obj);
PyAPI_FUNC(const char *) _PyProv_GetCurrentOwner(void);

/* Propagation */
PyAPI_FUNC(void) _PyProv_Propagate(PyObject *result, PyObject *a, PyObject *b);

/* Sink logging */
PyAPI_FUNC(void) _PyProv_LogIfSensitive(const char *sink, PyObject *obj);

/* Clear the thread-local current owner */
PyAPI_FUNC(void) _PyProv_ClearCurrentOwner(void);
PyAPI_FUNC(void) _PyProv_ClearObject(PyObject *obj);


#endif /* Py_PROVENANCE_H */
