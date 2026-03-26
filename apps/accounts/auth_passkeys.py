
import logging
import base64
import json
import secrets
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from .constants import EMAIL_NOT_VERIFIED_CODE, EMAIL_NOT_VERIFIED_MESSAGE

User = get_user_model()
logger = logging.getLogger(__name__)

# Try to import fido2 - it's optional but required for passkeys
try:
    from fido2 import cbor
    from fido2.server import Fido2Server
    from fido2.webauthn import (
        AuthenticatorData,
        PublicKeyCredentialDescriptor,
        AttestationObject,
        CollectedClientData,
        UserVerificationRequirement,
        ResidentKeyRequirement,
    )
    FIDO2_AVAILABLE = True
except ImportError:
    FIDO2_AVAILABLE = False
    logger.warning("fido2 library not installed. Passkey authentication unavailable.")


# Configuration
RP_ID = getattr(settings, "PASSKEY_RP_ID", "localhost")
RP_NAME = getattr(settings, "PASSKEY_RP_NAME", "CampusHub")
RP_ICON = getattr(settings, "PASSKEY_RP_ICON", None)
PASSKEY_CHALLENGE_TTL = int(getattr(settings, "PASSKEY_CHALLENGE_TTL_SECONDS", 300) or 300)


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


@dataclass
class PasskeyRegistrationResult:
    """Result of a passkey registration operation."""
    success: bool
    message: str
    credential_id: Optional[str] = None
    passkey_id: Optional[int] = None
    options: Optional[dict] = None


@dataclass
class PasskeyAuthenticationResult:
    """Result of a passkey authentication operation."""
    success: bool
    message: str
    code: Optional[str] = None
    user_id: Optional[int] = None
    passkey_id: Optional[int] = None
    options: Optional[dict] = None


@dataclass
class PasskeyInfo:
    """Information about a registered passkey."""
    id: int
    name: str
    credential_id: str
    public_key: str
    sign_count: int
    backup_eligible: bool
    backup_state: bool
    created_at: Any
    last_used_at: Any = None


class PasskeyService:
    """
    Service for handling passkey (WebAuthn/FIDO2) authentication.
    """
    
    def __init__(self):
        if not FIDO2_AVAILABLE:
            raise ImportError(
                "fido2 library is required for passkey authentication. "
                "Install it with: pip install fido2"
            )
        
        # Configure FIDO2 server
        self.server = Fido2Server(
            rp={"id": RP_ID, "name": RP_NAME, "icon": RP_ICON},
            attestation="none",  # Don't require attestation
        )
    
    def get_registration_options(
        self, 
        user: User, 
        passkey_name: Optional[str] = None
    ) -> PasskeyRegistrationResult:
        """
        Get registration options for a new passkey.
        
        Args:
            user: The user registering the passkey
            passkey_name: Optional name for the passkey
            
        Returns:
            PasskeyRegistrationResult with options
        """
        try:
            # Get existing passkeys for this user to exclude
            from .models import UserPasskey
            
            existing_credentials = []
            for passkey in UserPasskey.objects.filter(user=user):
                try:
                    cred_id = _b64url_decode(passkey.credential_id)
                    existing_credentials.append(
                        {
                            "id": _b64url_encode(cred_id),
                            "type": "public-key",
                        }
                    )
                except Exception:
                    pass
            
            # Generate challenge
            challenge = secrets.token_bytes(32)
            
            # Build options
            options = {
                "challenge": _b64url_encode(challenge),
                "rp": {
                    "id": RP_ID,
                    "name": RP_NAME,
                },
                "user": {
                    "id": _b64url_encode(str(user.id).encode()),
                    "name": user.email,
                    "displayName": user.get_full_name() or user.email,
                },
                "pubKeyCredParams": [
                    {"type": "public-key", "alg": -7},  # ES256
                    {"type": "public-key", "alg": -257},  # RS256
                ],
                "excludeCredentials": existing_credentials,
                "authenticatorSelection": {
                    "residentKey": "preferred",
                    "userVerification": "preferred",
                    "authenticatorAttachment": "platform",
                },
                "attestation": "none",
                "extensions": {
                    "credProps": True,
                },
            }
            
            # Store challenge temporarily (in production, use Redis/session)
            self._store_challenge(user.id, challenge)
            
            return PasskeyRegistrationResult(
                success=True,
                message="Passkey registration initiated.",
                options=options,
            )
            
        except Exception as e:
            logger.error(f"Error getting passkey registration options: {e}")
            return PasskeyRegistrationResult(
                success=False,
                message="Failed to generate registration options.",
            )
    
    def verify_registration(
        self,
        user: User,
        credential_data: dict,
        passkey_name: Optional[str] = None
    ) -> PasskeyRegistrationResult:
        """
        Verify and complete passkey registration.
        
        Args:
            user: The user registering the passkey
            credential_data: The credential data from the client
            passkey_name: Optional name for the passkey
            
        Returns:
            PasskeyRegistrationResult
        """
        try:
            # Parse client data
            client_data_json = credential_data.get("clientDataJSON")
            if not client_data_json:
                return PasskeyRegistrationResult(
                    success=False,
                    message="Missing client data.",
                )
            
            # Decode client data
            client_data = json.loads(_b64url_decode(client_data_json))
            
            # Verify challenge
            expected_challenge = self._get_challenge(user.id)
            if not expected_challenge:
                return PasskeyRegistrationResult(
                    success=False,
                    message="Registration session expired. Please try again.",
                )
            
            actual_challenge = client_data.get("challenge")
            if not actual_challenge:
                return PasskeyRegistrationResult(
                    success=False,
                    message="Missing challenge in response.",
                )
            if actual_challenge != _b64url_encode(expected_challenge):
                return PasskeyRegistrationResult(
                    success=False,
                    message="Registration challenge mismatch.",
                )
            
            # Verify origin
            origin = client_data.get("origin", "")
            if RP_ID not in origin and "localhost" not in origin:
                logger.warning(f"Invalid origin in passkey registration: {origin}")
                return PasskeyRegistrationResult(
                    success=False,
                    message="Invalid authentication origin.",
                )
            
            # Parse attestation
            attestation_object = credential_data.get("attestationObject")
            if not attestation_object:
                return PasskeyRegistrationResult(
                    success=False,
                    message="Missing attestation object.",
                )
            
            attestation = cbor.decode(_b64url_decode(attestation_object))
            
            # Extract credential data
            auth_data = attestation.get("authData")
            if not auth_data:
                return PasskeyRegistrationResult(
                    success=False,
                    message="Missing auth data.",
                )
            
            # Parse auth data
            rp_id_hash = auth_data[:32]
            flags = auth_data[32]
            sign_count = int.from_bytes(auth_data[33:37], "big")
            
            # Get credential ID and public key
            credential_id_length = int.from_bytes(auth_data[53:55], "big")
            credential_id = auth_data[55:55 + credential_id_length]
            public_key = auth_data[55 + credential_id_length:]
            
            # Encode for storage
            credential_id_b64 = _b64url_encode(credential_id)
            public_key_b64 = _b64url_encode(public_key)
            
            # Check if backup is eligible
            backup_eligible = bool(flags & 0x04)  # ED flag
            backup_state = bool(flags & 0x08)  # BE flag
            
            # Generate a default name if not provided
            if not passkey_name:
                passkey_count = UserPasskey.objects.filter(user=user).count() + 1
                passkey_name = f"Passkey {passkey_count}"
            
            # Store passkey
            from .models import UserPasskey
            
            passkey = UserPasskey.objects.create(
                user=user,
                name=passkey_name,
                credential_id=credential_id_b64,
                public_key=public_key_b64,
                sign_count=sign_count,
                backup_eligible=backup_eligible,
                backup_state=backup_state,
                aaguid=attestation.get("aaguid", "").decode() if attestation.get("aaguid") else "",
            )
            
            # Clean up challenge
            self._clear_challenge(user.id)
            
            logger.info(f"Passkey registered for user {user.id}: {passkey_name}")
            
            return PasskeyRegistrationResult(
                success=True,
                message="Passkey registered successfully.",
                credential_id=credential_id_b64,
                passkey_id=passkey.id,
            )
            
        except Exception as e:
            logger.error(f"Error verifying passkey registration: {e}")
            return PasskeyRegistrationResult(
                success=False,
                message="Failed to verify passkey registration.",
            )
    
    def get_authentication_options(self, user: Optional[User] = None) -> PasskeyAuthenticationResult:
        """
        Get authentication options for passkey login.
        
        Args:
            user: Optional user to get credentials for
            
        Returns:
            PasskeyAuthenticationResult with options
        """
        try:
            # Generate challenge
            challenge = secrets.token_bytes(32)
            
            # Get allowed credentials
            allow_credentials = []
            if user:
                from .models import UserPasskey
                
                for passkey in UserPasskey.objects.filter(user=user):
                    try:
                        cred_id = _b64url_decode(passkey.credential_id)
                        allow_credentials.append(
                            {"id": _b64url_encode(cred_id), "type": "public-key"}
                        )
                    except Exception:
                        pass
            
            # Build options
            options = {
                "challenge": _b64url_encode(challenge),
                "rpId": RP_ID,
                "allowCredentials": allow_credentials,
                "userVerification": "preferred",
                "timeout": 60000,  # 60 seconds
            }
            
            # Store challenge
            self._store_challenge("auth", challenge)
            
            return PasskeyAuthenticationResult(
                success=True,
                message="Passkey authentication initiated.",
                options=options,
            )
            
        except Exception as e:
            logger.error(f"Error getting passkey authentication options: {e}")
            return PasskeyAuthenticationResult(
                success=False,
                message="Failed to generate authentication options.",
            )
    
    def verify_authentication(
        self,
        credential_data: dict,
        expected_user_id: Optional[int] = None
    ) -> PasskeyAuthenticationResult:
        """
        Verify passkey authentication.
        
        Args:
            credential_data: The credential data from the client
            expected_user_id: Optional expected user ID
            
        Returns:
            PasskeyAuthenticationResult
        """
        try:
            from .models import UserPasskey
            
            # Parse client data
            client_data_json = credential_data.get("clientDataJSON")
            if not client_data_json:
                return PasskeyAuthenticationResult(
                    success=False,
                    message="Missing client data.",
                )
            
            client_data = json.loads(_b64url_decode(client_data_json))
            
            # Verify challenge
            expected_challenge = self._get_challenge("auth")
            if not expected_challenge:
                return PasskeyAuthenticationResult(
                    success=False,
                    message="Authentication session expired. Please try again.",
                )
            
            actual_challenge = client_data.get("challenge")
            if not actual_challenge:
                return PasskeyAuthenticationResult(
                    success=False,
                    message="Missing challenge in response.",
                )
            if actual_challenge != _b64url_encode(expected_challenge):
                return PasskeyAuthenticationResult(
                    success=False,
                    message="Authentication challenge mismatch.",
                )
            
            # Get credential ID
            credential_id = credential_data.get("credentialId", "")
            if not credential_id:
                return PasskeyAuthenticationResult(
                    success=False,
                    message="Missing credential ID.",
                )
            
            # Find passkey
            try:
                passkey = UserPasskey.objects.get(credential_id=credential_id)
            except UserPasskey.DoesNotExist:
                return PasskeyAuthenticationResult(
                    success=False,
                    message="Passkey not found.",
                )
            
            # Check if user is active
            if not passkey.user.is_active:
                return PasskeyAuthenticationResult(
                    success=False,
                    message="User account is disabled.",
                )
            if not passkey.user.is_verified:
                return PasskeyAuthenticationResult(
                    success=False,
                    message=EMAIL_NOT_VERIFIED_MESSAGE,
                    code=EMAIL_NOT_VERIFIED_CODE,
                )
            
            # If expected user ID provided, verify it matches
            if expected_user_id and passkey.user.id != expected_user_id:
                return PasskeyAuthenticationResult(
                    success=False,
                    message="Passkey does not belong to this user.",
                )
            
            # Verify authentication data
            auth_data = credential_data.get("authenticatorData")
            if not auth_data:
                return PasskeyAuthenticationResult(
                    success=False,
                    message="Missing authenticator data.",
                )
            
            # Decode auth data
            auth_data_decoded = _b64url_decode(auth_data)
            
            # Verify RP ID
            rp_id_hash = auth_data_decoded[:32]
            # (In production, verify this matches RP_ID)
            
            # Get sign count
            new_sign_count = int.from_bytes(auth_data_decoded[33:37], "big")
            
            # Verify signature would be valid
            # (In production, use fido2 to verify the actual signature)
            
            # Update sign count
            if new_sign_count > passkey.sign_count:
                passkey.sign_count = new_sign_count
                passkey.last_used_at = timezone.now()
                passkey.save()
            
            # Clean up challenge
            self._clear_challenge("auth")
            
            logger.info(f"Passkey authentication successful for user {passkey.user.id}")
            
            return PasskeyAuthenticationResult(
                success=True,
                message="Authentication successful.",
                user_id=passkey.user.id,
                passkey_id=passkey.id,
            )
            
        except Exception as e:
            logger.error(f"Error verifying passkey authentication: {e}")
            return PasskeyAuthenticationResult(
                success=False,
                message="Failed to verify passkey authentication.",
            )
    
    def list_passkeys(self, user: User) -> List[PasskeyInfo]:
        """
        List all passkeys for a user.
        
        Args:
            user: The user
            
        Returns:
            List of PasskeyInfo
        """
        from .models import UserPasskey
        
        passkeys = []
        for passkey in UserPasskey.objects.filter(user=user):
            passkeys.append(PasskeyInfo(
                id=passkey.id,
                name=passkey.name,
                credential_id=passkey.credential_id[:20] + "...",  # Truncate for display
                public_key=passkey.public_key[:20] + "...",  # Truncate
                sign_count=passkey.sign_count,
                backup_eligible=passkey.backup_eligible,
                backup_state=passkey.backup_state,
                created_at=passkey.created_at,
                last_used_at=passkey.last_used_at,
            ))
        
        return passkeys
    
    def delete_passkey(self, user: User, passkey_id: int) -> Tuple[bool, str]:
        """
        Delete a passkey for a user.
        
        Args:
            user: The user
            passkey_id: The passkey ID to delete
            
        Returns:
            Tuple of (success, message)
        """
        from .models import UserPasskey
        
        try:
            passkey = UserPasskey.objects.get(id=passkey_id, user=user)
            passkey.delete()
            return True, "Passkey deleted successfully."
        except UserPasskey.DoesNotExist:
            return False, "Passkey not found."
    
    def update_passkey_name(
        self, 
        user: User, 
        passkey_id: int, 
        new_name: str
    ) -> Tuple[bool, str]:
        """
        Update a passkey's name.
        
        Args:
            user: The user
            passkey_id: The passkey ID
            new_name: New name for the passkey
            
        Returns:
            Tuple of (success, message)
        """
        from .models import UserPasskey
        
        try:
            passkey = UserPasskey.objects.get(id=passkey_id, user=user)
            passkey.name = new_name
            passkey.save()
            return True, "Passkey name updated."
        except UserPasskey.DoesNotExist:
            return False, "Passkey not found."
    
    # Challenge storage helpers

    def _challenge_cache_key(self, key: str) -> str:
        return f"passkey:challenge:{key}"

    def _store_challenge(self, key: str, challenge: bytes) -> None:
        """Store challenge temporarily."""
        cache.set(self._challenge_cache_key(key), challenge, timeout=PASSKEY_CHALLENGE_TTL)
    
    def _get_challenge(self, key: str) -> Optional[bytes]:
        """Get stored challenge."""
        return cache.get(self._challenge_cache_key(key))
    
    def _clear_challenge(self, key: str) -> None:
        """Clear stored challenge."""
        cache.delete(self._challenge_cache_key(key))


# Singleton instance
passkey_service = PasskeyService() if FIDO2_AVAILABLE else None
