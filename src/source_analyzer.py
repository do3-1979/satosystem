#!/usr/bin/env python3
"""
ソースコード解析ツール

Pythonソースファイルからクラス・関数・メソッド情報を抽出し、
JSON形式で docs/analysis/ に保存します。

スキーマ: docs/analysis/SOURCE_ANALYSIS_SCHEMA.json
"""

import os
import ast
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


class SourceAnalyzer:
    """Pythonソースコードを解析するクラス"""
    
    def __init__(self, source_file: str):
        """
        SourceAnalyzerの初期化

        Args:
            source_file: 解析対象のPythonファイルパス
        """
        self.source_file = source_file
        self.tree = None
        self.source_lines = []
        
        # ファイルを読み込みASTを生成
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                self.source_code = f.read()
                self.source_lines = self.source_code.split('\n')
                self.tree = ast.parse(self.source_code)
        except Exception as e:
            print(f"❌ ファイル読み込みエラー ({source_file}): {e}")
            raise

    def extract_docstring(self, node: ast.AST) -> Optional[str]:
        """ノードからdocstringを抽出"""
        return ast.get_docstring(node)

    def get_line_count(self) -> int:
        """コード行数を取得"""
        return len([line for line in self.source_lines if line.strip() and not line.strip().startswith('#')])

    def analyze_imports(self) -> List[Dict[str, Any]]:
        """インポート情報を抽出"""
        imports = []
        
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "module": alias.name,
                        "type": "standard" if '.' not in alias.name else "local",
                        "used_for": f"Module: {alias.name}"
                    })
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                for alias in node.names:
                    imports.append({
                        "module": f"{module_name}.{alias.name}" if module_name else alias.name,
                        "type": "local",
                        "used_for": f"From {module_name}"
                    })
        
        return imports

    def analyze_parameters(self, node: ast.arguments) -> List[Dict[str, Any]]:
        """関数・メソッドのパラメータを抽出"""
        params = []
        
        # 通常のパラメータ
        for arg in node.args:
            params.append({
                "name": arg.arg,
                "type": self._extract_annotation(arg.annotation),
                "description": f"Parameter: {arg.arg}"
            })
        
        # デフォルト値付きパラメータ
        num_defaults = len(node.defaults)
        if num_defaults > 0:
            # デフォルト値は最後のパラメータから逆順に対応
            default_start = len(node.args) - num_defaults
            for i, default in enumerate(node.defaults):
                param_index = default_start + i
                if param_index < len(params):
                    params[param_index]["default"] = self._extract_value(default)
        
        # *args と **kwargs
        if node.vararg:
            params.append({
                "name": f"*{node.vararg.arg}",
                "type": "args"
            })
        if node.kwarg:
            params.append({
                "name": f"**{node.kwarg.arg}",
                "type": "kwargs"
            })
        
        return params

    def _extract_annotation(self, annotation: Optional[ast.expr]) -> str:
        """型アノテーションを文字列で取得"""
        if annotation is None:
            return "Any"
        
        try:
            return ast.unparse(annotation)
        except:
            return "Any"

    def _extract_value(self, value: ast.expr) -> Any:
        """デフォルト値を取得"""
        if isinstance(value, ast.Constant):
            return value.value
        elif isinstance(value, ast.List):
            return "[]"
        elif isinstance(value, ast.Dict):
            return "{}"
        else:
            return None

    def analyze_methods(self, class_node: ast.ClassDef) -> List[Dict[str, Any]]:
        """クラスのメソッドを解析"""
        methods = []
        
        for item in class_node.body:
            if isinstance(item, ast.FunctionDef):
                method_info = {
                    "name": item.name,
                    "line": item.lineno,
                    "visibility": "private" if item.name.startswith('_') else "public",
                    "is_classmethod": any(isinstance(d, ast.Name) and d.id == 'classmethod' for d in item.decorator_list),
                    "is_staticmethod": any(isinstance(d, ast.Name) and d.id == 'staticmethod' for d in item.decorator_list),
                    "signature": self._generate_signature(item),
                    "parameters": self.analyze_parameters(item.args),
                    "return_type": self._extract_annotation(item.returns),
                    "docstring": self.extract_docstring(item) or "No description",
                    "summary": (self.extract_docstring(item) or "").split('\n')[0] if self.extract_docstring(item) else item.name
                }
                
                # メソッド内の関数呼び出しを抽出
                calls = self._extract_method_calls(item)
                if calls:
                    method_info["calls"] = calls
                
                methods.append(method_info)
        
        return methods

    def _generate_signature(self, node: ast.FunctionDef) -> str:
        """関数/メソッドのシグネチャを生成"""
        try:
            return f"def {node.name}{ast.unparse(node.args)}"
        except:
            return f"def {node.name}(...)"

    def _extract_method_calls(self, node: ast.FunctionDef) -> List[str]:
        """メソッド内で呼び出されている関数を抽出"""
        calls = []
        
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    calls.append(f"{ast.unparse(child.func.value)}.{child.func.attr}")
                elif isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
        
        return list(set(calls))  # 重複を削除

    def analyze_classes(self) -> List[Dict[str, Any]]:
        """クラスを解析"""
        classes = []
        
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef):
                # トップレベルのクラスのみ（ネストされたクラスは除外）
                if hasattr(node, 'parent'):
                    continue
                
                class_info = {
                    "name": node.name,
                    "line": node.lineno,
                    "docstring": self.extract_docstring(node) or "No description",
                    "inheritance": [ast.unparse(base) for base in node.bases] if node.bases else [],
                    "methods": self.analyze_methods(node)
                }
                
                classes.append(class_info)
        
        return classes

    def analyze_functions(self) -> List[Dict[str, Any]]:
        """トップレベルの関数を解析"""
        functions = []
        
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    "name": node.name,
                    "line": node.lineno,
                    "visibility": "private" if node.name.startswith('_') else "public",
                    "signature": self._generate_signature(node),
                    "parameters": self.analyze_parameters(node.args),
                    "return_type": self._extract_annotation(node.returns),
                    "docstring": self.extract_docstring(node) or "No description",
                    "summary": (self.extract_docstring(node) or "").split('\n')[0] if self.extract_docstring(node) else node.name
                }
                functions.append(func_info)
        
        return functions

    def analyze_constants(self) -> List[Dict[str, Any]]:
        """定数を解析（UPPERCASE変数）"""
        constants = []
        
        for node in self.tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        constants.append({
                            "name": target.id,
                            "value": self._extract_value(node.value),
                            "type": type(self._extract_value(node.value)).__name__,
                            "description": f"Constant: {target.id}"
                        })
        
        return constants

    def generate_report(self) -> Dict[str, Any]:
        """解析結果をまとめたレポートを生成"""
        classes = self.analyze_classes()
        functions = self.analyze_functions()
        
        # メソッド数をカウント
        total_methods = sum(len(c["methods"]) for c in classes)
        
        report = {
            "metadata": {
                "source_file": self.source_file,
                "analyzed_at": datetime.now().isoformat(),
                "python_version": f"{sys.version_info.major}.{sys.version_info.minor}"
            },
            "file_info": {
                "path": self.source_file,
                "description": "Source code structure analysis"
            },
            "imports": self.analyze_imports(),
            "classes": classes,
            "functions": functions,
            "constants": self.analyze_constants(),
            "summary": {
                "total_classes": len(classes),
                "total_methods": total_methods,
                "total_functions": len(functions),
                "total_constants": len(self.analyze_constants()),
                "lines_of_code": self.get_line_count()
            }
        }
        
        return report


def analyze_single_file(source_file: str, output_dir: str = "docs/analysis") -> bool:
    """
    単一のPythonファイルを解析してJSONで保存

    Args:
        source_file: 解析対象ファイル
        output_dir: 出力ディレクトリ

    Returns:
        成功したかどうか
    """
    try:
        analyzer = SourceAnalyzer(source_file)
        report = analyzer.generate_report()
        
        # 出力ファイル名を生成（src/example.py → example.json）
        filename = Path(source_file).stem + ".json"
        # 絶対パスで出力ディレクトリを構築（ワークスペースルートベース）
        workspace_root = Path(__file__).parent.parent
        output_path = os.path.join(workspace_root, output_dir, filename)
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # JSONを保存
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"✅ {source_file} → {output_path}")
        return True
    except Exception as e:
        print(f"❌ {source_file}: {e}")
        return False


def analyze_all_files(src_dir: str = "src", output_dir: str = "docs/analysis") -> None:
    """
    指定ディレクトリのすべてのPythonファイルを解析

    Args:
        src_dir: ソースディレクトリ
        output_dir: 出力ディレクトリ
    """
    print(f"\n{'='*80}")
    print(f"🔍 ソースコード解析: {src_dir} → {output_dir}")
    print(f"{'='*80}\n")
    
    py_files = sorted(Path(src_dir).glob("*.py"))
    
    if not py_files:
        print(f"❌ .py ファイルが見つかりません: {src_dir}")
        return
    
    success_count = 0
    fail_count = 0
    
    for py_file in py_files:
        # __pycache__ など不要なファイルをスキップ
        if py_file.name.startswith('__'):
            continue
        
        if analyze_single_file(str(py_file), output_dir):
            success_count += 1
        else:
            fail_count += 1
    
    print(f"\n{'='*80}")
    print(f"📊 解析完了: 成功 {success_count}, 失敗 {fail_count}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="ソースコード解析ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  python source_analyzer.py                    # src/ のすべてのファイルを解析
  python source_analyzer.py --file src/bot.py  # 単一ファイルを解析
  python source_analyzer.py --dir src/utils/   # 指定ディレクトリを解析
        """
    )
    
    parser.add_argument(
        "--file",
        help="解析する単一ファイル"
    )
    
    parser.add_argument(
        "--dir",
        default="src",
        help="解析するディレクトリ（デフォルト: src）"
    )
    
    parser.add_argument(
        "--output",
        default="docs/analysis",
        help="出力ディレクトリ（デフォルト: docs/analysis）"
    )
    
    args = parser.parse_args()
    
    if args.file:
        analyze_single_file(args.file, args.output)
    else:
        analyze_all_files(args.dir, args.output)
