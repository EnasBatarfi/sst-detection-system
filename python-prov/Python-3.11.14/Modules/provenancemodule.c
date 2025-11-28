// #define PY_SSIZE_T_CLEAN
// #include "Python.h"
// #include "provenance.h"

// /* Python wrapper for _PyProv_SetCurrentOwner */
// static PyObject *
// py_set_current_owner(PyObject *self, PyObject *args)
// {
//     const char *email;
//     if (!PyArg_ParseTuple(args, "s:set_current_owner", &email))
//         return NULL;
//     _PyProv_SetCurrentOwner(email);
//     Py_RETURN_NONE;
// }

// /* Optional: expose a getter for debugging */
// static PyObject *
// py_get_current_owner(PyObject *self, PyObject *Py_UNUSED(ignored))
// {
//     const char *owner = _PyProv_GetCurrentOwner();
//     if (!owner) owner = "<none>";
//     return PyUnicode_FromString(owner);
// }

// static PyMethodDef ProvMethods[] = {
//     {"set_current_owner", py_set_current_owner, METH_VARARGS,
//      "Set the current provenance owner (email)."},
//     {"get_current_owner", py_get_current_owner, METH_NOARGS,
//      "Return the current provenance owner for this thread."},
//     {NULL, NULL, 0, NULL}
// };

// static struct PyModuleDef provmodule = {
//     PyModuleDef_HEAD_INIT,
//     "provenance",     /* name as seen in import provenance */
//     "Provenance tagging runtime bindings",
//     -1,
//     ProvMethods
// };

// PyMODINIT_FUNC
// PyInit_provenance(void)
// {
//     return PyModule_Create(&provmodule);
// }
