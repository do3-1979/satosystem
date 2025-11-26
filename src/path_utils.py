"""
Path utilities for satosystem.

Provides consistent path resolution regardless of working directory.
All paths are converted to absolute paths based on project root detection.
"""

import os
from pathlib import Path


class PathManager:
    """Centralized path management for the project."""
    
    _project_root = None
    _src_dir = None
    
    @classmethod
    def get_project_root(cls):
        """
        Get project root directory.
        
        Tries to find the directory containing .git, otherwise falls back
        to the parent of src/ directory.
        
        Returns:
            Path: Absolute path to project root
        """
        if cls._project_root is not None:
            return cls._project_root
        
        # Try to find .git directory
        current = Path(__file__).resolve().parent.parent
        while current != current.parent:
            if (current / '.git').exists():
                cls._project_root = current
                return cls._project_root
            current = current.parent
        
        # Fallback: parent of src/
        cls._project_root = Path(__file__).resolve().parent.parent
        return cls._project_root
    
    @classmethod
    def get_src_dir(cls):
        """Get src directory path."""
        if cls._src_dir is not None:
            return cls._src_dir
        cls._src_dir = cls.get_project_root() / 'src'
        return cls._src_dir
    
    @classmethod
    def get_api_key_file(cls):
        """
        Get API key file path.
        
        Returns:
            Path: Absolute path to src/.api_key
        """
        return cls.get_src_dir() / '.api_key'
    
    @classmethod
    def get_config_file(cls):
        """
        Get main config file path.
        
        Returns:
            Path: Absolute path to src/config.ini
        """
        return cls.get_src_dir() / 'config.ini'
    
    @classmethod
    def get_config_template_file(cls):
        """
        Get config template file path.
        
        Returns:
            Path: Absolute path to src/config.template.ini
        """
        return cls.get_src_dir() / 'config.template.ini'
    
    @classmethod
    def get_report_dir(cls):
        """
        Get report directory path.
        
        Returns:
            Path: Absolute path to report/
        """
        return cls.get_project_root() / 'report'
    
    @classmethod
    def get_logs_dir(cls):
        """
        Get logs directory path (project root).
        
        Returns:
            Path: Absolute path to logs/
        """
        return cls.get_project_root() / 'logs'
    
    @classmethod
    def get_src_logs_dir(cls):
        """
        Get logs directory path (src/).
        
        Returns:
            Path: Absolute path to src/logs/
        """
        return cls.get_src_dir() / 'logs'
    
    @classmethod
    def get_output_configs_dir(cls):
        """
        Get output configs directory path.
        
        Returns:
            Path: Absolute path to output_configs/
        """
        return cls.get_project_root() / 'output_configs'
    
    @classmethod
    def get_analysis_dir(cls):
        """
        Get analysis directory path.
        
        Returns:
            Path: Absolute path to analysis/
        """
        return cls.get_project_root() / 'analysis'
    
    @classmethod
    def get_work_reports_dir(cls):
        """
        Get work reports directory path.
        
        Returns:
            Path: Absolute path to work_reports/
        """
        return cls.get_project_root() / 'work_reports'
    
    @classmethod
    def get_docs_dir(cls):
        """
        Get docs directory path.
        
        Returns:
            Path: Absolute path to docs/
        """
        return cls.get_project_root() / 'docs'
    
    @classmethod
    def ensure_dir_exists(cls, directory):
        """
        Ensure directory exists, creating it if necessary.
        
        Args:
            directory: Path-like object or string
            
        Returns:
            Path: The directory path
        """
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @classmethod
    def to_absolute_path(cls, relative_path):
        """
        Convert relative path to absolute path based on project root.
        
        Args:
            relative_path: Path relative to project root
            
        Returns:
            Path: Absolute path
        """
        if isinstance(relative_path, str):
            relative_path = Path(relative_path)
        
        if relative_path.is_absolute():
            return relative_path
        
        return cls.get_project_root() / relative_path


def load_api_keys_from_file():
    """
    Load API keys from .api_key file.
    
    Returns:
        tuple: (api_key, api_secret) or (None, None) if not found
    """
    api_key_file = PathManager.get_api_key_file()
    
    if not api_key_file.exists():
        return None, None
    
    try:
        api_key = None
        api_secret = None
        
        with open(api_key_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key == 'api_key':
                        api_key = value
                    elif key == 'api_secret':
                        api_secret = value
                else:
                    # Support format: key_value on a single line
                    if line.startswith('api_key'):
                        api_key = line.split('=', 1)[1].strip() if '=' in line else None
                    elif line.startswith('api_secret'):
                        api_secret = line.split('=', 1)[1].strip() if '=' in line else None
        
        return api_key, api_secret
    
    except Exception as e:
        print(f"[WARN] Error reading API keys from {api_key_file}: {e}")
        return None, None
