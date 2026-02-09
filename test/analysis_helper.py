"""
分析JSONファイル互換性ヘルパー

format_version 1.0 と 2.0 の両方に対応するユーティリティ
"""

import json


def load_analysis_with_compat(filepath):
    """
    分析JSONファイルを読み込み、形式を自動判定して統一インターフェースを返す
    
    Args:
        filepath: 分析JSONファイルのパス
        
    Returns:
        dict: 統一形式の分析データ
            {
                "format_version": str,
                "source_file": str,
                "classes": [
                    {
                        "name": str,
                        "methods": [
                            {
                                "name": str,
                                "is_classmethod": bool,
                                "is_staticmethod": bool,
                                "is_private": bool,
                                ...
                            }
                        ],
                        ...
                    }
                ]
            }
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 新形式（format_version 2.0）の判定
    if "metadata" in data and "format_version" in data.get("metadata", {}):
        return _convert_v2_to_compat(data)
    
    # 旧形式（format_version 1.0 または明示的バージョンなし）
    return _convert_v1_to_compat(data)


def _convert_v2_to_compat(data):
    """format_version 2.0 を統一形式に変換"""
    result = {
        "format_version": data["metadata"].get("format_version", "2.0"),
        "source_file": data["metadata"].get("source_file", ""),
        "classes": []
    }
    
    # クラス情報がある場合（現在の2.0形式にはclassesがない場合がある）
    if "classes" in data:
        result["classes"] = data["classes"]
    
    return result


def _convert_v1_to_compat(data):
    """format_version 1.0 を統一形式に変換"""
    result = {
        "format_version": data.get("format_version", "1.0"),
        "source_file": data.get("source_file", ""),
        "classes": data.get("classes", [])
    }
    
    return result


def get_class_methods(analysis, class_index=0):
    """
    分析データから指定クラスのメソッド一覧を取得
    
    Args:
        analysis: load_analysis_with_compat() の返り値
        class_index: クラスのインデックス（デフォルト: 0）
        
    Returns:
        list: メソッド情報のリスト
    """
    classes = analysis.get("classes", [])
    if not classes or class_index >= len(classes):
        return []
    
    return classes[class_index].get("methods", [])


def get_class_method_names(analysis, class_index=0):
    """
    分析データから指定クラスのメソッド名一覧を取得
    
    Args:
        analysis: load_analysis_with_compat() の返り値
        class_index: クラスのインデックス（デフォルト: 0）
        
    Returns:
        set: メソッド名のセット
    """
    methods = get_class_methods(analysis, class_index)
    return {m["name"] for m in methods}


def get_classmethods(analysis, class_index=0):
    """
    分析データから指定クラスのクラスメソッド一覧を取得
    
    Args:
        analysis: load_analysis_with_compat() の返り値
        class_index: クラスのインデックス（デフォルト: 0）
        
    Returns:
        list: クラスメソッド名のリスト
    """
    methods = get_class_methods(analysis, class_index)
    return [m["name"] for m in methods if m.get("is_classmethod", False)]


def get_private_methods(analysis, class_index=0):
    """
    分析データから指定クラスのプライベートメソッド一覧を取得
    
    Args:
        analysis: load_analysis_with_compat() の返り値
        class_index: クラスのインデックス（デフォルト: 0）
        
    Returns:
        list: プライベートメソッド名のリスト
    """
    methods = get_class_methods(analysis, class_index)
    return [m["name"] for m in methods if m["name"].startswith("_")]
