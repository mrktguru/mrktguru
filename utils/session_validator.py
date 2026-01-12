"""
Session File Validator for Telethon session files

Validates session files before accepting them into the system.
Checks file size, format, integrity, and extracts metadata.
"""

import os
import sqlite3
import struct
from datetime import datetime
from typing import Dict, Any, Optional


class SessionValidator:
    """Validator for Telethon session files"""
    
    # Constants
    MAX_FILE_SIZE = 100 * 1024  # 100KB
    MIN_FILE_SIZE = 1024  # 1KB
    
    def validate_session_file(self, filepath: str) -> Dict[str, Any]:
        """
        Validate session file integrity and safety
        
        Args:
            filepath: Path to session file
            
        Returns:
            dict: {
                'valid': bool,
                'error': str or None,
                'size': int,
                'format': str,
                'warnings': list
            }
        """
        result = {
            'valid': False,
            'error': None,
            'size': 0,
            'format': 'unknown',
            'warnings': []
        }
        
        try:
            # 1. Check file exists
            if not os.path.exists(filepath):
                result['error'] = 'File not found'
                return result
            
            # 2. Check file size
            size = os.path.getsize(filepath)
            result['size'] = size
            
            if size == 0:
                result['error'] = 'Empty file'
                return result
            
            if size < self.MIN_FILE_SIZE:
                result['error'] = f'File too small ({size} bytes)'
                return result
            
            if size > self.MAX_FILE_SIZE:
                result['error'] = f'File too large ({size} bytes, max {self.MAX_FILE_SIZE})'
                return result
            
            # 3. Check if it's a valid SQLite database
            try:
                conn = sqlite3.connect(filepath)
                cursor = conn.cursor()
                
                # Check SQLite integrity
                cursor.execute("PRAGMA integrity_check")
                integrity = cursor.fetchone()
                
                if integrity[0] != 'ok':
                    result['error'] = f'SQLite integrity check failed: {integrity[0]}'
                    conn.close()
                    return result
                
                # Check for required Telethon tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                required_tables = ['sessions', 'entities', 'sent_files', 'update_state']
                missing_tables = [t for t in required_tables if t not in tables]
                
                if missing_tables:
                    result['warnings'].append(f'Missing tables: {", ".join(missing_tables)}')
                    # Not critical - old Telethon versions may have different schema
                
                # Check sessions table structure
                if 'sessions' in tables:
                    cursor.execute("PRAGMA table_info(sessions)")
                    columns = [row[1] for row in cursor.fetchall()]
                    
                    required_columns = ['dc_id', 'server_address', 'port', 'auth_key']
                    missing_columns = [c for c in required_columns if c not in columns]
                    
                    if missing_columns:
                        result['error'] = f'Invalid session format - missing columns: {", ".join(missing_columns)}'
                        conn.close()
                        return result
                    
                    result['format'] = 'telethon_sqlite'
                else:
                    result['error'] = 'Missing sessions table - not a valid Telethon session'
                    conn.close()
                    return result
                
                conn.close()
                
            except sqlite3.Error as e:
                result['error'] = f'Not a valid SQLite database: {str(e)}'
                return result
            
            # 4. All checks passed
            result['valid'] = True
            return result
            
        except Exception as e:
            result['error'] = f'Validation error: {str(e)}'
            return result
    
    def extract_metadata(self, filepath: str) -> Dict[str, Any]:
        """
        Extract metadata from session file
        
        Args:
            filepath: Path to session file
            
        Returns:
            dict: Session metadata including device info, age estimation, etc.
        """
        metadata = {
            'dc_id': None,
            'server_address': None,
            'port': None,
            'has_auth_key': False,
            'entities_count': 0,
            'sent_files_count': 0,
            'file_created': None,
            'file_modified': None,
            'estimated_age': 'unknown',
            'suspicious': False,
            'suspicious_reasons': []
        }
        
        try:
            # File timestamps
            stat = os.stat(filepath)
            metadata['file_created'] = datetime.fromtimestamp(stat.st_ctime).isoformat()
            metadata['file_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            
            # SQLite data
            conn = sqlite3.connect(filepath)
            cursor = conn.cursor()
            
            # Get session info
            cursor.execute("SELECT dc_id, server_address, port, auth_key FROM sessions LIMIT 1")
            row = cursor.fetchone()
            
            if row:
                metadata['dc_id'] = row[0]
                metadata['server_address'] = row[1]
                metadata['port'] = row[2]
                metadata['has_auth_key'] = row[3] is not None and len(row[3]) > 0
            
            # Count entities (contacts, channels, etc.)
            try:
                cursor.execute("SELECT COUNT(*) FROM entities")
                metadata['entities_count'] = cursor.fetchone()[0]
            except:
                pass
            
            # Count sent files
            try:
                cursor.execute("SELECT COUNT(*) FROM sent_files")
                metadata['sent_files_count'] = cursor.fetchone()[0]
            except:
                pass
            
            conn.close()
            
            # Estimate account age based on activity
            metadata['estimated_age'] = self._estimate_age(metadata)
            
            # Check for suspicious patterns
            metadata['suspicious'], metadata['suspicious_reasons'] = self._check_suspicious(metadata, filepath)
            
        except Exception as e:
            metadata['error'] = str(e)
        
        return metadata
    
    def _estimate_age(self, metadata: Dict[str, Any]) -> str:
        """
        Estimate account age based on metadata
        
        Returns:
            'new' (< 3 days), 'young' (3-30 days), 'mature' (> 30 days), 'unknown'
        """
        entities_count = metadata.get('entities_count', 0)
        sent_files_count = metadata.get('sent_files_count', 0)
        
        # Heuristics based on activity
        if entities_count == 0 and sent_files_count == 0:
            return 'new'  # No activity = likely new
        
        if entities_count < 5 and sent_files_count < 3:
            return 'new'  # Very low activity = new
        
        if entities_count < 20 and sent_files_count < 10:
            return 'young'  # Some activity = young
        
        if entities_count >= 20 or sent_files_count >= 10:
            return 'mature'  # Significant activity = mature
        
        return 'unknown'
    
    def _check_suspicious(self, metadata: Dict[str, Any], filepath: str) -> tuple:
        """
        Check for suspicious patterns in session
        
        Returns:
            (is_suspicious: bool, reasons: list)
        """
        reasons = []
        
        # Check 1: No auth key
        if not metadata.get('has_auth_key'):
            reasons.append('no_auth_key')
        
        # Check 2: Invalid DC
        dc_id = metadata.get('dc_id')
        if dc_id and (dc_id < 1 or dc_id > 5):
            reasons.append(f'invalid_dc_{dc_id}')
        
        # Check 3: File too old (> 1 year)
        try:
            file_created = metadata.get('file_created')
            if file_created:
                created_dt = datetime.fromisoformat(file_created)
                age_days = (datetime.now() - created_dt).days
                
                if age_days > 365:
                    reasons.append(f'very_old_file_{age_days}_days')
        except:
            pass
        
        # Check 4: Suspicious file size patterns
        size = os.path.getsize(filepath)
        if size < 2048:  # Very small
            reasons.append('suspiciously_small')
        
        is_suspicious = len(reasons) > 0
        
        return is_suspicious, reasons
    
    def get_account_age_category(self, metadata: Dict[str, Any]) -> str:
        """
        Get account age category for verification strategy
        
        Returns:
            'new', 'young', or 'mature'
        """
        estimated_age = metadata.get('estimated_age', 'unknown')
        
        if estimated_age == 'unknown':
            # Conservative approach - treat as new
            return 'new'
        
        return estimated_age
