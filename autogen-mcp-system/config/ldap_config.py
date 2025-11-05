from ldap3 import Server, Connection, ALL
from config.settings import settings
from loguru import logger
from typing import Tuple, Optional, List


class LDAPManager:
    """Manages LDAP connections and authentication"""

    def __init__(self):
        self.server = Server(
            settings.ldap_server,
            port=settings.ldap_port,
            use_ssl=settings.ldap_use_ssl,
            get_info=ALL,
        )

    def authenticate_user(
        self, username: str, password: str
    ) -> Tuple[bool, Optional[dict]]:
        """
        Authenticate user against LDAP
        Returns: (success: bool, user_info: dict or None)
        """
        try:
            user_dn = settings.ldap_user_dn_pattern.format(
                username=username, base_dn=settings.ldap_base_dn
            )

            conn = Connection(
                self.server, user=user_dn, password=password, auto_bind=True
            )

            logger.info(f"User {username} authenticated successfully")

            # Retrieve user groups/attributes
            user_info = self._get_user_info(conn, username)
            conn.unbind()

            return True, user_info

        except Exception as e:
            logger.warning(f"Authentication failed for user {username}: {str(e)}")
            return False, None

    def _get_user_info(self, conn: Connection, username: str) -> dict:
        """Get user information including groups"""
        try:
            search_filter = f"(sAMAccountName={username})"
            conn.search(
                search_base=settings.ldap_base_dn,
                search_filter=search_filter,
                attributes=["mail", "displayName", "memberOf"],
            )

            if conn.entries:
                entry = conn.entries[0]
                return {
                    "username": username,
                    "email": str(entry.mail.value) if entry.mail else None,
                    "display_name": (
                        str(entry.displayName.value) if entry.displayName else username
                    ),
                    "groups": (
                        [str(g) for g in entry.memberOf.values]
                        if entry.memberOf
                        else []
                    ),
                }
            return {"username": username}
        except Exception as e:
            logger.error(f"Error retrieving user info: {e}")
            return {"username": username}


ldap_manager = LDAPManager()
