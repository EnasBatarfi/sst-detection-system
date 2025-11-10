"""
Runtime Instrumentation - Main entry point for SST detection system
Combines execution tracing, import hooks, and AST transformation
"""
try:
    from sst_detection_system.execution_tracer import ExecutionTracer
    from sst_detection_system.import_hook import SSTImportHook
    from sst_detection_system.ast_transformer import SSTASTTransformer
except ImportError:
    from execution_tracer import ExecutionTracer
    from import_hook import SSTImportHook
    from ast_transformer import SSTASTTransformer


class RuntimeInstrumentation:
    """
    Main class that orchestrates all runtime instrumentation techniques
    """
    
    def __init__(self, 
                 enable_tracing=True,
                 enable_import_hook=True,
                 enable_ast_transformation=True,
                 instrumented_modules=None,
                 excluded_modules=None):
        """
        Initialize runtime instrumentation
        
        Args:
            enable_tracing: Use sys.settrace for execution tracing
            enable_import_hook: Use import hooks to instrument modules
            enable_ast_transformation: Transform AST at import time
            instrumented_modules: List of module patterns to instrument
            excluded_modules: List of module patterns to exclude
        """
        self.enable_tracing = enable_tracing
        self.enable_import_hook = enable_import_hook
        self.enable_ast_transformation = enable_ast_transformation
        
        self.execution_tracer = ExecutionTracer() if enable_tracing else None
        self.import_hook = SSTImportHook(
            enabled_modules=instrumented_modules,
            exclude_modules=excluded_modules
        ) if enable_import_hook else None
        
        self.enabled = False
    
    def start(self):
        """Start all enabled instrumentation"""
        if self.enabled:
            return
        
        if self.enable_tracing and self.execution_tracer:
            self.execution_tracer.start()
        
        if self.enable_import_hook and self.import_hook:
            self.import_hook.install()
        
        self.enabled = True
        print("[RuntimeInstrumentation] All instrumentation started")
    
    def stop(self):
        """Stop all instrumentation"""
        if not self.enabled:
            return
        
        if self.execution_tracer:
            self.execution_tracer.stop()
        
        if self.import_hook:
            self.import_hook.uninstall()
        
        self.enabled = False
        print("[RuntimeInstrumentation] All instrumentation stopped")
    
    def configure(self, **kwargs):
        """Configure instrumentation settings"""
        if 'enable_tracing' in kwargs:
            self.enable_tracing = kwargs['enable_tracing']
        if 'enable_import_hook' in kwargs:
            self.enable_import_hook = kwargs['enable_import_hook']
        if 'enable_ast_transformation' in kwargs:
            self.enable_ast_transformation = kwargs['enable_ast_transformation']
        
        # Restart if already enabled
        if self.enabled:
            self.stop()
            self.start()
