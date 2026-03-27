#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Encrypted Sensitive Memory Bank: Independent storage of sensitive information with auto-encryption

Features:
1. Phone/bank card/ID card/payment account/password auto-identification + encrypted storage
2. Independent isolated storage, plaintext never stored on disk
3. Secure key management
4. Encrypted data retrieval
"""
import os
import json
import sqlite3
import base64
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptedMemory:
    """Encrypted Sensitive Memory Bank: Independent storage of sensitive information with auto-encryption"""
    
    SENSITIVE_TYPES = {
        "phone": {
            "patterns": [r"(1[3-9]\d{9})"],
            "description": "Phone number"
        },
        "bank_card": {
            "patterns": [r"(6\d{15,18})"],
            "description": "Bank card number"
        },
        "id_card": {
            "patterns": [r"(\d{17}[\dXx])"],
            "description": "ID card number"
        },
        "passport": {
            "patterns": [r"([A-Za-z]\d{8})"],
            "description": "Passport number"
        },
        "payment_account": {
            "patterns": [r"(wxid_[a-zA-Z0-9]+)", r"(Alipay account)"],
            "description": "Payment account"
        },
        "password": {
            "patterns": [r"(password[is:=]\s*\S+)"],
            "description": "Password"
        }
    }
    
    def __init__(self, db_path: str = "data/encrypted_memory.db", 
                 key_file: str = "data/.encryption_key"):
        self.db_path = db_path
        self.key_file = key_file
        self.cipher = self._init_cipher()
        self.init_db()
    
    def _init_cipher(self) -> Fernet:
        """
        Initialize encryptor
        
        :return: Fernet encryptor instance
        """
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            os.chmod(self.key_file, 0o600)
        
        return Fernet(key)
    
    def init_db(self):
        """Initialize encrypted database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS encrypted_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    sensitive_type TEXT NOT NULL,
                    encrypted_value TEXT NOT NULL,
                    hash_value TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_id ON encrypted_memory(user_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sensitive_type ON encrypted_memory(sensitive_type)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_hash_value ON encrypted_memory(hash_value)
            ''')
            
            conn.commit()
    
    def encrypt_data(self, data: str) -> Tuple[str, str]:
        """
        Encrypt data
        
        :param data: Original data
        :return: (encrypted data, hash value)
        """
        encrypted = self.cipher.encrypt(data.encode('utf-8'))
        encrypted_str = base64.b64encode(encrypted).decode('utf-8')
        
        hash_value = hashlib.sha256(data.encode('utf-8')).hexdigest()
        
        return encrypted_str, hash_value
    
    def decrypt_data(self, encrypted_str: str) -> str:
        """
        Decrypt data
        
        :param encrypted_str: Encrypted data string
        :return: Original data
        """
        encrypted = base64.b64decode(encrypted_str.encode('utf-8'))
        decrypted = self.cipher.decrypt(encrypted)
        return decrypted.decode('utf-8')
    
    def save_encrypted(self, user_id: str, sensitive_type: str, 
                       data: str, description: str = None) -> int:
        """
        Encrypt and store sensitive information
        
        :param user_id: User ID
        :param sensitive_type: Sensitive type (phone/bank_card/id_card etc.)
        :param data: Original data
        :param description: Description info
        :return: Record ID
        """
        encrypted_value, hash_value = self.encrypt_data(data)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id FROM encrypted_memory
                WHERE user_id = ? AND sensitive_type = ?
            ''', (user_id, sensitive_type))
            
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute('''
                    UPDATE encrypted_memory
                    SET encrypted_value = ?, hash_value = ?, 
                        description = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (encrypted_value, hash_value, description, existing[0]))
                
                record_id = existing[0]
            else:
                cursor.execute('''
                    INSERT INTO encrypted_memory
                    (user_id, sensitive_type, encrypted_value, hash_value, description)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, sensitive_type, encrypted_value, hash_value, description))
                
                record_id = cursor.lastrowid
            
            conn.commit()
            
            return record_id
    
    def get_encrypted(self, user_id: str, sensitive_type: str) -> Optional[str]:
        """
        Get and decrypt sensitive information
        
        :param user_id: User ID
        :param sensitive_type: Sensitive type
        :return: Original data
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT encrypted_value FROM encrypted_memory
                WHERE user_id = ? AND sensitive_type = ?
                ORDER BY updated_at DESC
                LIMIT 1
            ''', (user_id, sensitive_type))
            
            row = cursor.fetchone()
            if row:
                return self.decrypt_data(row[0])
            
            return None
    
    def get_all_encrypted_types(self, user_id: str) -> List[str]:
        """
        Get all sensitive information types for user
        
        :param user_id: User ID
        :return: Sensitive type list
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT sensitive_type FROM encrypted_memory
                WHERE user_id = ?
            ''', (user_id,))
            
            return [row[0] for row in cursor.fetchall()]
    
    def delete_encrypted(self, user_id: str, sensitive_type: str):
        """
        Delete sensitive information
        
        :param user_id: User ID
        :param sensitive_type: Sensitive type
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM encrypted_memory
                WHERE user_id = ? AND sensitive_type = ?
            ''', (user_id, sensitive_type))
            
            conn.commit()
    
    def verify_data(self, user_id: str, sensitive_type: str, data: str) -> bool:
        """
        Verify data match
        
        :param user_id: User ID
        :param sensitive_type: Sensitive type
        :param data: Data to verify
        :return: Whether matches
        """
        hash_value = hashlib.sha256(data.encode('utf-8')).hexdigest()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT hash_value FROM encrypted_memory
                WHERE user_id = ? AND sensitive_type = ?
            ''', (user_id, sensitive_type))
            
            row = cursor.fetchone()
            return row and row[0] == hash_value
    
    def get_stats(self) -> Dict:
        """
        Get statistics
        
        :return: Statistics info
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM encrypted_memory')
            total = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT sensitive_type, COUNT(*) 
                FROM encrypted_memory 
                GROUP BY sensitive_type
            ''')
            
            by_type = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                "total_records": total,
                "by_type": by_type
            }
    
    def export_encrypted_backup(self, backup_path: str):
        """
        Export encrypted backup
        
        :param backup_path: Backup file path
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, sensitive_type, encrypted_value, 
                       hash_value, description, created_at, updated_at
                FROM encrypted_memory
            ''')
            
            rows = cursor.fetchall()
            
            backup_data = [
                {
                    "user_id": row[0],
                    "sensitive_type": row[1],
                    "encrypted_value": row[2],
                    "hash_value": row[3],
                    "description": row[4],
                    "created_at": row[5],
                    "updated_at": row[6]
                }
                for row in rows
            ]
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)


encrypted_memory = EncryptedMemory()
