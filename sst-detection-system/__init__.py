"""
SST Detection System - Runtime-Level Instrumentation
Modifies Python runtime to track data flow without monkey patching.
"""
try:
    from sst_detection_system.runtime_instrumentation import RuntimeInstrumentation
    from sst_detection_system.import_hook import SSTImportHook
    from sst_detection_system.ast_transformer import SSTASTTransformer
    from sst_detection_system.execution_tracer import ExecutionTracer
except ImportError:
    from runtime_instrumentation import RuntimeInstrumentation
    from import_hook import SSTImportHook
    from ast_transformer import SSTASTTransformer
    from execution_tracer import ExecutionTracer

__all__ = [
    'RuntimeInstrumentation',
    'SSTImportHook',
    'SSTASTTransformer',
    'ExecutionTracer',
]
