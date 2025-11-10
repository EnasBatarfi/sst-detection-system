"""
AST Transformer - Rewrites Python code at import time to inject tracking
"""
import ast
from typing import Any, Optional


class SSTASTTransformer(ast.NodeTransformer):
    """
    Transforms Python AST to inject data tracking and provenance calls
    """
    
    def __init__(self):
        self.tracker_imported = False
    
    def visit_Module(self, node: ast.Module) -> ast.Module:
        """Visit module node and add imports"""
        # Add import for tracking functions
        if not self.tracker_imported:
            import_node = ast.ImportFrom(
                module='sst_detection_system.runtime_tagger',
                names=[
                    ast.alias(name='tag_value', asname='_tag_value'),
                    ast.alias(name='check_and_tag', asname='_check_and_tag'),
                ],
                level=0
            )
            node.body.insert(0, import_node)
            self.tracker_imported = True
        
        # Visit all statements
        self.generic_visit(node)
        return node
    
    def visit_Call(self, node: ast.Call) -> ast.Call:
        """Visit function calls and inject tracking"""
        # Check if this is an external API call
        if self._is_external_api_call(node):
            # Wrap the call with tracking
            return self._wrap_external_call(node)
        
        # Check if this is a data operation
        if self._is_data_operation(node):
            return self._wrap_data_operation(node)
        
        self.generic_visit(node)
        return node
    
    def visit_Assign(self, node: ast.Assign) -> ast.Assign:
        """Visit assignments and tag values if they contain personal data"""
        self.generic_visit(node)
        
        # Check if assigned value might contain personal data
        for target in node.targets:
            if isinstance(target, ast.Name):
                # Add tagging call after assignment
                tag_call = self._create_tag_call(target.id, node.value)
                if tag_call:
                    # We can't insert after in AST, so we'll handle this differently
                    # For now, we'll wrap the value
                    if isinstance(node.value, (ast.Str, ast.Constant)):
                        node.value = self._wrap_value_with_tagging(node.value, target.id)
        
        return node
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        """Visit function definitions and add parameter tagging"""
        self.generic_visit(node)
        
        # Add tagging for function parameters
        tagging_statements = []
        for arg in node.args.args:
            if arg.arg != 'self':  # Skip self
                tag_call = ast.Expr(
                    value=ast.Call(
                        func=ast.Name(id='_check_and_tag', ctx=ast.Load()),
                        args=[ast.Name(id=arg.arg, ctx=ast.Load())],
                        keywords=[]
                    )
                )
                tagging_statements.append(tag_call)
        
        # Insert tagging at the beginning of function
        if tagging_statements:
            node.body = tagging_statements + node.body
        
        return node
    
    def _is_external_api_call(self, node: ast.Call) -> bool:
        """Check if this is a call to an external API"""
        if isinstance(node.func, ast.Attribute):
            # Check for requests.post, requests.get, etc.
            if isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id
                if module_name in ['requests', 'urllib', 'http']:
                    return True
                if 'openai' in module_name.lower() or 'groq' in module_name.lower():
                    return True
            
            # Check method names
            if node.func.attr in ['post', 'get', 'put', 'delete', 'request', 'urlopen', 'create']:
                return True
        
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in ['post', 'get', 'put', 'delete', 'request', 'urlopen']:
                return True
        
        return False
    
    def _is_data_operation(self, node: ast.Call) -> bool:
        """Check if this is a data operation (database, file, etc.)"""
        if isinstance(node.func, ast.Attribute):
            # Database operations
            if node.func.attr in ['add', 'commit', 'query', 'filter', 'execute']:
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id in ['db', 'session']:
                        return True
            
            # File operations
            if node.func.attr == 'open' and 'w' in str(node):
                return True
        
        return False
    
    def _wrap_external_call(self, node: ast.Call) -> ast.Call:
        """Wrap external API call with tracking"""
        # Create a wrapper function call
        wrapper = ast.Call(
            func=ast.Name(id='_track_external_call', ctx=ast.Load()),
            args=[node],
            keywords=[]
        )
        return wrapper
    
    def _wrap_data_operation(self, node: ast.Call) -> ast.Call:
        """Wrap data operation with tracking"""
        wrapper = ast.Call(
            func=ast.Name(id='_track_data_operation', ctx=ast.Load()),
            args=[node],
            keywords=[]
        )
        return wrapper
    
    def _create_tag_call(self, var_name: str, value_node: ast.AST) -> Optional[ast.Expr]:
        """Create a call to tag a value"""
        return ast.Expr(
            value=ast.Call(
                func=ast.Name(id='_check_and_tag', ctx=ast.Load()),
                args=[ast.Name(id=var_name, ctx=ast.Load())],
                keywords=[]
            )
        )
    
    def _wrap_value_with_tagging(self, value_node: ast.AST, var_name: str) -> ast.Call:
        """Wrap a value with a tagging call"""
        return ast.Call(
            func=ast.Name(id='_tag_value', ctx=ast.Load()),
            args=[value_node],
            keywords=[ast.keyword(arg='var_name', value=ast.Str(s=var_name))]
        )
