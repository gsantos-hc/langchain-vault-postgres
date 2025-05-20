# Copyright (c) HashiCorp, Inc.
# SPDX-License-Identifier: MIT

import datetime
import logging
import os
import threading
from typing import Any, Callable, Dict, Optional

from hvac import Client
from requests import Session

SIDECAR_TOKEN_PATH = "/vault/secrets/token"


def get_vault_client(vault_addr: str, correlation_id: str) -> Client:
    # See if we have a token from a Vault Agent sidecar
    if os.path.exists(SIDECAR_TOKEN_PATH):
        with open(SIDECAR_TOKEN_PATH, "r") as f:
            token = f.read().strip()
    else:
        token = os.environ.get("VAULT_TOKEN", "")

    client = Client(url=vault_addr, token=token)

    # Make sure that Correlation IDs are passed through
    rs = Session()
    rs.headers["X-Correlation-ID"] = correlation_id
    client.session = rs

    # Check if we have a valid token
    if not client.is_authenticated():
        raise RuntimeError("Could not find a valid Vault token.")

    return client


class DynamicDatabaseSecret:
    """
    Manage a Vault dynamic database credential lease, automatically renewing in
    the background, rotating to a fresh lease if renewal fails, and revoking
    on exit.
    """

    def __init__(
        self,
        client: Client,
        role_name: str,
        mount_point: str = "database",
        renew_pct: float = 0.7,
        min_interval: int = 5,
        callback: Optional[Callable] = None,
    ):
        """
        :param client: Authenticated hvac.Client
        :param role_name: The name of the DB role in Vault
        :param mount_point: Vault database mount point (default "database")
        :param renew_margin: Fraction of TTL before renewal (e.g. 0.7 means renew at 70% of TTL)
        :param min_interval: Minimum interval between renewals in seconds
        :param callback: Optional callback function to call if a new lease is acquired
        """
        self._client = client
        self._role_name = role_name
        self._mount_point = mount_point
        self._renew_pct = renew_pct
        self._min_interval = min_interval
        self._callback = callback

        self._lease_id: Optional[str] = None
        self._lease_duration: Optional[int] = None
        self._lease_expires: Optional[datetime.datetime] = None
        self._renewable: bool = False
        self._credentials: Optional[Dict[str, str]] = None

        self._stop_event = threading.Event()
        self._renew_thread: Optional[threading.Thread] = None

    # Public properties ----------------------------------------------------------------
    @property
    def lease_id(self) -> Optional[str]:
        return self._lease_id

    @property
    def lease_duration(self) -> Optional[int]:
        return self._lease_duration

    @property
    def lease_expiration(self) -> str:
        """ISO 8601 formatted string of the lease expiration time."""
        if self._lease_expires is None:
            return ""
        return datetime.datetime.isoformat(self._lease_expires)

    @property
    def credentials(self) -> Optional[Dict[str, str]]:
        return self._credentials

    @property
    def is_running(self) -> bool:
        return self._renew_thread is not None and self._renew_thread.is_alive()

    # Public methods -------------------------------------------------------------------
    def acquire(self) -> Dict[str, str]:
        """
        Fetch a new credential lease from Vault, replacing any existing one.
        Returns the new credentials dict.
        """
        try:
            request_time = datetime.datetime.now(datetime.timezone.utc)
            resp = self._client.secrets.database.generate_credentials(
                name=self._role_name,
                mount_point=self._mount_point,
            )
            self._lease_id = resp["lease_id"]
            self._lease_duration = resp["lease_duration"]
            self._renewable = resp["renewable"]
            self._lease_expires = request_time + datetime.timedelta(
                seconds=self._lease_duration or 0
            )
            self._credentials = resp["data"]
        except Exception as exc:
            logging.exception("Failed to acquire new database credentials: %s", exc)
            raise

        if not isinstance(self._credentials, dict):
            raise ValueError(
                "Invalid credentials format: expected a dictionary, got %s",
                type(self._credentials),
            )

        logging.info(
            "Acquired new lease %s with duration %d seconds",
            self._lease_id,
            self._lease_duration,
        )

        return self._credentials

    def start(self) -> None:
        """Start the renewer thread."""
        if self._lease_id is None:
            raise RuntimeError("Cannot start renewer thread without an active lease.")
        if not self._renewable:
            raise RuntimeError("Lease is not renewable.")

        self._stop_event.clear()
        self._renew_thread = threading.Thread(target=self._renew_loop, daemon=True)
        self._renew_thread.start()

    def stop(self) -> None:
        """Stop the renewer thread and wait for it to finish."""
        self._stop_event.set()
        if self._renew_thread:
            try:
                self._renew_thread.join()
            except RuntimeError as exc:
                if "cannot join current thread" not in str(exc):
                    raise
                pass

    def revoke(self) -> None:
        """Revoke the active lease so Vault immediately deletes the credential."""
        if self._lease_id:
            try:
                self._client.sys.revoke_lease(self._lease_id)
                logging.info("Revoked lease %s", self._lease_id)
                self._lease_id = None
                self._lease_duration = None
                self._lease_expires = None
                self._renewable = False
                self._credentials = None
            except Exception:
                logging.exception("Failed to revoke lease %s", self._lease_id)

    # Renew loop -----------------------------------------------------------------------
    def next_renew_interval(self) -> float:
        """
        How long to wait before attempting renewal. Recomputed each loop so
        if lease_duration was updated on renew, we adapt.
        """
        return max(self._renew_pct * (self._lease_duration or 0), self._min_interval)

    def _renew_loop(self) -> None:
        """
        Background-renewer thread:
        - wait until it's time to renew,
        - try renewing;
        - if renewal fails, attempt a full new acquire() instead;
        - repeat until stopped.
        """
        while not self._stop_event.wait(timeout=self.next_renew_interval()):
            try:
                if not self._renewable:
                    raise RuntimeError(f"Lease {self._lease_id} is not renewable")

                # Request lease renewal
                request_time = datetime.datetime.now(datetime.timezone.utc)
                resp = self._client.sys.renew_lease(self._lease_id)

                # Update internal lease state
                self._lease_duration = resp.get("lease_duration", self._lease_duration)
                self._lease_expires = request_time + datetime.timedelta(
                    seconds=self._lease_duration or 0
                )
                logging.info(
                    "Renewed lease %s for the next %d seconds",
                    self._lease_id,
                    self._lease_duration,
                )

                # Check if the lease is still renewable
                if "warnings" in resp and isinstance(resp["warnings"], list):
                    if any("TTL value is capped" in w for w in resp["warnings"]):
                        self._renewable = False
                        logging.warning(
                            "Lease %s has reached its max TTL and is no longer renewable",
                            self._lease_id,
                        )
            except Exception as exc:
                # renewal failed → lease expired or otherwise invalid → get a fresh one
                logging.error("Could not renew lease %s: %s", self._lease_id, exc)
                try:
                    self.stop()
                    self.acquire()
                    self.start()
                except Exception as exc:
                    logging.error("Failed to get new credentials, giving up: %s", exc)
                    break

                if self._callback:
                    self._callback(creds=self, thread=self._renew_thread)

    # Context manager ------------------------------------------------------------------
    def __enter__(self) -> "DynamicDatabaseSecret":
        # acquire initial lease, start renewing, and hand back self
        self.acquire()
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # tear down: stop renewing, then revoke
        self.stop()
        self.revoke()

    # Signal handling ------------------------------------------------------------------
    def _signal_handler(self, signum: int, frame: Any) -> None:
        logging.info("Received signal %d, stopping renewer thread", signum)
        self.stop()
        self.revoke()
