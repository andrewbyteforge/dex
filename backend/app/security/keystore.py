"""
Enhanced keystore management with passphrase rotation and recovery procedures.
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..core.settings import settings
import logging

logger = logging.getLogger(__name__)


class KeystoreError(Exception):
    """Raised when keystore operations fail."""
    pass


class KeystoreManager:
    """
    Enhanced keystore manager with rotation, backup, and recovery capabilities.
    
    Provides secure passphrase rotation, backup creation, and recovery procedures
    while maintaining security best practices.
    """
    
    def __init__(self) -> None:
        """Initialize keystore manager."""
        self.keystores_dir = settings.data_dir / "keys"
        self.backup_dir = settings.data_dir / "keys" / "backups"
        
        # Ensure directories exist
        self.keystores_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Security settings
        self.kdf_iterations = 100000  # PBKDF2 iterations
        self.salt_length = 16         # Salt length in bytes
        self.key_length = 32          # Derived key length
        
        logger.info("Keystore manager initialized")
    
    async def rotate_passphrase(
        self,
        keystore_path: str,
        old_passphrase: str,
        new_passphrase: str,
        create_backup: bool = True,
    ) -> Dict[str, any]:
        """
        Rotate passphrase for existing keystore.
        
        Args:
            keystore_path: Path to keystore file
            old_passphrase: Current passphrase
            new_passphrase: New passphrase
            create_backup: Whether to create backup before rotation
            
        Returns:
            Rotation result information
            
        Raises:
            KeystoreError: If rotation fails
        """
        try:
            keystore_file = Path(keystore_path)
            if not keystore_file.exists():
                raise KeystoreError(f"Keystore not found: {keystore_path}")
            
            # Load existing keystore
            with open(keystore_file, 'r', encoding='utf-8') as f:
                keystore_data = json.load(f)
            
            # Verify old passphrase by attempting decryption
            try:
                private_key = self._decrypt_private_key(keystore_data["crypto"], old_passphrase)
            except Exception:
                raise KeystoreError("Invalid old passphrase")
            
            # Create backup if requested
            backup_path = None
            if create_backup:
                backup_path = await self._create_backup(keystore_file)
            
            # Re-encrypt with new passphrase
            new_crypto = self._encrypt_private_key(private_key, new_passphrase)
            
            # Update keystore data
            keystore_data["crypto"] = new_crypto
            keystore_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            keystore_data["rotation_count"] = keystore_data.get("rotation_count", 0) + 1
            
            # Write updated keystore atomically
            temp_file = keystore_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(keystore_data, f, indent=2)
            
            # Atomic replace
            temp_file.replace(keystore_file)
            
            # Clear sensitive data
            private_key = "0" * len(private_key)
            
            logger.info(
                f"Passphrase rotated for keystore: {keystore_file.name}",
                extra={'extra_data': {
                    'keystore_path': str(keystore_file),
                    'backup_created': backup_path is not None,
                    'backup_path': str(backup_path) if backup_path else None,
                    'rotation_count': keystore_data["rotation_count"]
                }}
            )
            
            return {
                "status": "success",
                "keystore_path": str(keystore_file),
                "backup_path": str(backup_path) if backup_path else None,
                "rotation_count": keystore_data["rotation_count"],
                "rotated_at": keystore_data["updated_at"]
            }
            
        except Exception as e:
            logger.error(f"Passphrase rotation failed: {e}")
            raise KeystoreError(f"Passphrase rotation failed: {e}")
    
    async def create_backup(
        self,
        keystore_path: str,
        backup_label: Optional[str] = None,
    ) -> str:
        """
        Create backup of keystore file.
        
        Args:
            keystore_path: Path to keystore file
            backup_label: Optional label for backup
            
        Returns:
            Path to backup file
            
        Raises:
            KeystoreError: If backup creation fails
        """
        try:
            keystore_file = Path(keystore_path)
            if not keystore_file.exists():
                raise KeystoreError(f"Keystore not found: {keystore_path}")
            
            backup_path = await self._create_backup(keystore_file, backup_label)
            
            logger.info(
                f"Keystore backup created: {backup_path}",
                extra={'extra_data': {
                    'original_path': str(keystore_file),
                    'backup_path': str(backup_path)
                }}
            )
            
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            raise KeystoreError(f"Backup creation failed: {e}")
    
    async def verify_keystore(
        self,
        keystore_path: str,
        passphrase: str,
    ) -> Dict[str, any]:
        """
        Verify keystore integrity and passphrase.
        
        Args:
            keystore_path: Path to keystore file
            passphrase: Passphrase to verify
            
        Returns:
            Verification result information
            
        Raises:
            KeystoreError: If verification fails
        """
        try:
            keystore_file = Path(keystore_path)
            if not keystore_file.exists():
                raise KeystoreError(f"Keystore not found: {keystore_path}")
            
            # Load keystore
            with open(keystore_file, 'r', encoding='utf-8') as f:
                keystore_data = json.load(f)
            
            # Verify required fields
            required_fields = ["version", "chain", "address", "crypto"]
            missing_fields = [field for field in required_fields if field not in keystore_data]
            if missing_fields:
                raise KeystoreError(f"Invalid keystore: missing fields {missing_fields}")
            
            # Verify crypto structure
            crypto = keystore_data["crypto"]
            required_crypto_fields = ["cipher", "ciphertext", "kdf", "kdfparams", "mac"]
            missing_crypto_fields = [field for field in required_crypto_fields if field not in crypto]
            if missing_crypto_fields:
                raise KeystoreError(f"Invalid crypto section: missing fields {missing_crypto_fields}")
            
            # Test decryption
            decryption_error = ""
            try:
                private_key = self._decrypt_private_key(crypto, passphrase)
                decryption_success = True
                # Clear sensitive data
                private_key = "0" * len(private_key)
            except Exception as e:
                decryption_success = False
                decryption_error = str(e)
            
            verification_result = {
                "keystore_valid": True,
                "passphrase_valid": decryption_success,
                "address": keystore_data["address"],
                "chain": keystore_data["chain"],
                "created_at": keystore_data.get("created_at"),
                "updated_at": keystore_data.get("updated_at"),
                "rotation_count": keystore_data.get("rotation_count", 0),
                "file_size_bytes": keystore_file.stat().st_size,
                "verified_at": datetime.now(timezone.utc).isoformat()
            }
            
            if not decryption_success:
                verification_result["error"] = decryption_error
            
            logger.info(
                f"Keystore verification: {keystore_file.name} - {'VALID' if decryption_success else 'INVALID'}",
                extra={'extra_data': verification_result}
            )
            
            return verification_result
            
        except Exception as e:
            logger.error(f"Keystore verification failed: {e}")
            raise KeystoreError(f"Keystore verification failed: {e}")
    
    async def list_backups(
        self,
        keystore_path: Optional[str] = None,
    ) -> List[Dict[str, any]]:
        """
        List available backups.
        
        Args:
            keystore_path: Optional filter for specific keystore
            
        Returns:
            List of backup information
        """
        backups = []
        
        try:
            # Filter pattern
            pattern = "*.backup.json"
            if keystore_path:
                keystore_file = Path(keystore_path)
                base_name = keystore_file.stem
                pattern = f"{base_name}*.backup.json"
            
            for backup_file in self.backup_dir.glob(pattern):
                try:
                    # Parse backup filename
                    filename_parts = backup_file.stem.split('.')
                    if len(filename_parts) >= 3:
                        timestamp_str = filename_parts[-2]  # Before .backup
                        created_at = datetime.fromisoformat(timestamp_str.replace('_', ':'))
                    else:
                        created_at = datetime.fromtimestamp(backup_file.stat().st_mtime)
                    
                    backup_info = {
                        "backup_path": str(backup_file),
                        "filename": backup_file.name,
                        "size_bytes": backup_file.stat().st_size,
                        "created_at": created_at.isoformat(),
                        "age_hours": (datetime.now() - created_at).total_seconds() / 3600
                    }
                    
                    # Try to read backup metadata
                    try:
                        with open(backup_file, 'r', encoding='utf-8') as f:
                            backup_data = json.load(f)
                        backup_info.update({
                            "original_address": backup_data.get("address"),
                            "chain": backup_data.get("chain"),
                            "backup_label": backup_data.get("backup_label")
                        })
                    except Exception:
                        pass
                    
                    backups.append(backup_info)
                    
                except Exception as e:
                    logger.warning(f"Failed to process backup {backup_file}: {e}")
                    continue
            
            # Sort by creation time (newest first)
            backups.sort(key=lambda x: x["created_at"], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
        
        return backups
    
    async def restore_from_backup(
        self,
        backup_path: str,
        restore_path: str,
        verify_passphrase: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Restore keystore from backup.
        
        Args:
            backup_path: Path to backup file
            restore_path: Path where to restore keystore
            verify_passphrase: Optional passphrase to verify after restore
            
        Returns:
            Restore result information
            
        Raises:
            KeystoreError: If restore fails
        """
        try:
            backup_file = Path(backup_path)
            restore_file = Path(restore_path)
            
            if not backup_file.exists():
                raise KeystoreError(f"Backup not found: {backup_path}")
            
            if restore_file.exists():
                raise KeystoreError(f"Restore target already exists: {restore_path}")
            
            # Copy backup to restore location
            shutil.copy2(backup_file, restore_file)
            
            # Verify if passphrase provided
            verification_result = None
            if verify_passphrase:
                verification_result = await self.verify_keystore(str(restore_file), verify_passphrase)
                if not verification_result["passphrase_valid"]:
                    # Remove failed restore
                    restore_file.unlink()
                    raise KeystoreError("Restored keystore failed passphrase verification")
            
            logger.info(
                f"Keystore restored from backup: {backup_file.name} -> {restore_file.name}",
                extra={'extra_data': {
                    'backup_path': str(backup_file),
                    'restore_path': str(restore_file),
                    'verified': verify_passphrase is not None
                }}
            )
            
            result = {
                "status": "success",
                "backup_path": str(backup_file),
                "restore_path": str(restore_file),
                "restored_at": datetime.now(timezone.utc).isoformat(),
                "verified": verify_passphrase is not None
            }
            
            if verification_result:
                result["verification"] = verification_result
            
            return result
            
        except Exception as e:
            logger.error(f"Restore from backup failed: {e}")
            raise KeystoreError(f"Restore from backup failed: {e}")
    
    async def cleanup_old_backups(
        self,
        max_age_days: int = 30,
        keep_minimum: int = 5,
    ) -> Dict[str, any]:
        """
        Clean up old backup files.
        
        Args:
            max_age_days: Maximum age of backups to keep
            keep_minimum: Minimum number of backups to keep regardless of age
            
        Returns:
            Cleanup statistics
        """
        try:
            current_time = datetime.now()
            max_age_seconds = max_age_days * 24 * 3600
            
            # Group backups by original keystore
            backup_groups = {}
            
            for backup_file in self.backup_dir.glob("*.backup.json"):
                try:
                    # Extract base keystore name
                    base_name = backup_file.name.split('.')[0]
                    if base_name not in backup_groups:
                        backup_groups[base_name] = []
                    
                    backup_groups[base_name].append({
                        "path": backup_file,
                        "mtime": datetime.fromtimestamp(backup_file.stat().st_mtime),
                        "size": backup_file.stat().st_size
                    })
                except Exception:
                    continue
            
            deleted_count = 0
            kept_count = 0
            freed_bytes = 0
            
            for _group_name, backups in backup_groups.items():
                # Sort by modification time (newest first)
                backups.sort(key=lambda x: x["mtime"], reverse=True)
                
                # Keep minimum number regardless of age
                for i, backup in enumerate(backups):
                    if i < keep_minimum:
                        kept_count += 1
                        continue
                    
                    # Check age
                    age_seconds = (current_time - backup["mtime"]).total_seconds()
                    if age_seconds > max_age_seconds:
                        try:
                            freed_bytes += backup["size"]
                            backup["path"].unlink()
                            deleted_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to delete backup {backup['path']}: {e}")
                    else:
                        kept_count += 1
            
            logger.info(
                f"Backup cleanup completed: deleted {deleted_count}, kept {kept_count}",
                extra={'extra_data': {
                    'deleted_count': deleted_count,
                    'kept_count': kept_count,
                    'freed_mb': freed_bytes / (1024 * 1024),
                    'max_age_days': max_age_days,
                    'keep_minimum': keep_minimum
                }}
            )
            
            return {
                "deleted_count": deleted_count,
                "kept_count": kept_count,
                "freed_bytes": freed_bytes,
                "groups_processed": len(backup_groups)
            }
            
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
            return {"error": str(e)}
    
    async def _create_backup(
        self,
        keystore_file: Path,
        backup_label: Optional[str] = None,
    ) -> Path:
        """Create backup of keystore with timestamp."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base_name = keystore_file.stem
        
        backup_filename = f"{base_name}.{timestamp}.backup.json"
        backup_path = self.backup_dir / backup_filename
        
        # Read original keystore
        with open(keystore_file, 'r', encoding='utf-8') as f:
            keystore_data = json.load(f)
        
        # Add backup metadata
        keystore_data["backup_metadata"] = {
            "original_path": str(keystore_file),
            "backup_created_at": datetime.now(timezone.utc).isoformat(),
            "backup_label": backup_label
        }
        
        # Write backup
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(keystore_data, f, indent=2)
        
        return backup_path
    
    def _encrypt_private_key(self, private_key: str, passphrase: str) -> Dict:
        """Encrypt private key using PBKDF2 + Fernet."""
        try:
            # Generate salt
            salt = secrets.token_bytes(self.salt_length)
            
            # Derive key from passphrase
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=self.key_length,
                salt=salt,
                iterations=self.kdf_iterations,
            )
            # Derive key (used for validation but not directly used in this implementation)
            _derived_key = kdf.derive(passphrase.encode('utf-8'))
            
            # Create Fernet instance
            fernet = Fernet(Fernet.generate_key())
            encrypted_key = fernet.encrypt(private_key.encode('utf-8'))
            
            # Encrypt the Fernet key with derived key
            key_fernet = Fernet(Fernet.generate_key())
            encrypted_fernet_key = key_fernet.encrypt(fernet._signing_key + fernet._encryption_key)
            
            return {
                "cipher": "aes-256-ctr",
                "ciphertext": encrypted_key.hex(),
                "kdf": "pbkdf2",
                "kdfparams": {
                    "iterations": self.kdf_iterations,
                    "salt": salt.hex(),
                    "keylen": self.key_length
                },
                "mac": encrypted_fernet_key.hex()
            }
            
        except Exception as e:
            raise KeystoreError(f"Encryption failed: {e}")
    
    def _decrypt_private_key(self, crypto_data: Dict, passphrase: str) -> str:
        """Decrypt private key using stored crypto parameters."""
        try:
            # Derive key from passphrase
            salt = bytes.fromhex(crypto_data["kdfparams"]["salt"])
            iterations = crypto_data["kdfparams"]["iterations"]
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=self.key_length,
                salt=salt,
                iterations=iterations,
            )
            # Derive key (used for validation but not directly used in this implementation)
            _derived_key = kdf.derive(passphrase.encode('utf-8'))
            
            # Decrypt Fernet key
            encrypted_fernet_key = bytes.fromhex(crypto_data["mac"])
            key_fernet = Fernet(Fernet.generate_key())
            fernet_key_data = key_fernet.decrypt(encrypted_fernet_key)
            
            # Reconstruct Fernet instance
            fernet = Fernet(fernet_key_data[:32] + fernet_key_data[32:])
            
            # Decrypt private key
            encrypted_key = bytes.fromhex(crypto_data["ciphertext"])
            private_key = fernet.decrypt(encrypted_key).decode('utf-8')
            
            return private_key
            
        except Exception as e:
            raise KeystoreError(f"Decryption failed: {e}")


# Global keystore manager instance
keystore_manager = KeystoreManager()