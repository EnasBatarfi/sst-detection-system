"""
Import Hook - Intercepts module imports to inject tracking code
Uses sys.meta_path to modify modules at import time.
"""
import sys
import importlib
import importlib.util
import types
from typing import Optional
import ast

try:
    from sst_detection_system.ast_transformer import SSTASTTransformer
except ImportError:
    from ast_transformer import SSTASTTransformer


class SSTImportHook:
    """
    Import hook that intercepts module loading and injects tracking code
    """
    
    def __init__(self, enabled_modules=None, exclude_modules=None):
        """
        Initialize import hook
        
        Args:
            enabled_modules: List of module patterns to instrument (None = all)
            exclude_modules: List of module patterns to exclude
        """
        self.enabled_modules = enabled_modules or []
        self.exclude_modules = exclude_modules or [
            'site-packages',
            'dist-packages',
            '__pycache__',
            'pytest',
            'unittest',
        ]
        self.ast_transformer = SSTASTTransformer()
        self._original_finders = []
        self.enabled = False
    
    def install(self):
        """Install the import hook"""
        if self.enabled:
            return
        
        # Insert our finder at the beginning of meta_path
        sys.meta_path.insert(0, self)
        self.enabled = True
        print("[SSTImportHook] Import hook installed")
    
    def uninstall(self):
        """Uninstall the import hook"""
        if not self.enabled:
            return
        
        if self in sys.meta_path:
            sys.meta_path.remove(self)
        self.enabled = False
        print("[SSTImportHook] Import hook uninstalled")
    
    def find_spec(self, name, path, target=None):
        """
        Part of the importlib.abc.MetaPathFinder interface
        Called by Python's import system
        """
        # Let other finders handle it first
        for finder in sys.meta_path[1:]:
            if finder is self:
                continue
            spec = finder.find_spec(name, path, target)
            if spec is not None and spec.loader is not None:
                # Check if we should instrument this module
                if self._should_instrument(spec):
                    # Wrap the loader to inject our code
                    spec.loader = InstrumentedLoader(spec.loader, self.ast_transformer)
                return spec
        return None
    
    def _should_instrument(self, spec) -> bool:
        """Determine if a module should be instrumented"""
        if spec.origin is None:
            return False
        
        origin = spec.origin
        
        # Exclude system modules
        if origin.startswith('<'):
            return False
        
        # Exclude excluded patterns
        for pattern in self.exclude_modules:
            if pattern in origin:
                return False
        
        # Check if enabled modules list is specified
        if self.enabled_modules:
            for pattern in self.enabled_modules:
                if pattern in origin:
                    return True
            return False
        
        # Default: instrument user code (not site-packages)
        return 'site-packages' not in origin and 'dist-packages' not in origin


class InstrumentedLoader:
    """
    Wraps a module loader to inject tracking code
    """
    
    def __init__(self, original_loader, ast_transformer):
        self.original_loader = original_loader
        self.ast_transformer = ast_transformer
    
    def create_module(self, spec):
        """Create module (optional)"""
        if hasattr(self.original_loader, 'create_module'):
            return self.original_loader.create_module(spec)
        return None
    
    def exec_module(self, module):
        """Execute module with instrumentation"""
        # Get the source code
        if hasattr(self.original_loader, 'get_source'):
            try:
                source = self.original_loader.get_source(module.__name__)
                if source:
                    # Transform the AST
                    try:
                        tree = ast.parse(source, filename=module.__file__)
                        transformed_tree = self.ast_transformer.visit(tree)
                        
                        # Compile and execute the transformed code
                        code = compile(transformed_tree, module.__file__, 'exec')
                        exec(code, module.__dict__)
                        return
                    except Exception as e:
                        print(f"[InstrumentedLoader] AST transformation failed for {module.__name__}: {e}")
                        # Fall back to original loader
            except Exception as e:
                print(f"[InstrumentedLoader] Could not get source for {module.__name__}: {e}")
        
        # Fall back to original loader
        if hasattr(self.original_loader, 'exec_module'):
            self.original_loader.exec_module(module)
        elif hasattr(self.original_loader, 'load_module'):
            self.original_loader.load_module(module.__name__)
