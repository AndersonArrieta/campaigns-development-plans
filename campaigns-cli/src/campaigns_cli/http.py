"""Fábrica de clientes HTTP (Cognito, fake channel y API de Kubernetes) a partir de Settings."""

import ssl
from functools import cached_property

import httpx

from campaigns_cli.output import warn
from campaigns_cli.settings import Settings

TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class HttpClients:
    """Crea los clientes solo cuando se piden por primera vez, como `AwsClients`.

    `transport` permite inyectar un `httpx.MockTransport` en las pruebas.
    """

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport

    @cached_property
    def cognito(self) -> httpx.Client:
        return httpx.Client(timeout=TIMEOUT, transport=self.transport)

    @cached_property
    def fake_channel(self) -> httpx.Client:
        verify = self.settings.fake_channel_verify_ssl
        if not verify:
            warn("FAKE_CHANNEL_VERIFY_SSL=false: no se verifica el certificado del fake channel.")
        return httpx.Client(timeout=TIMEOUT, verify=verify, transport=self.transport)

    def kubernetes(self, endpoint: str, ca_pem: str, auth: httpx.Auth) -> httpx.Client:
        """Cliente de la API de un clúster: verifica el certificado con la CA del propio clúster."""
        context = ssl.create_default_context(cadata=ca_pem)
        return httpx.Client(
            base_url=endpoint, timeout=TIMEOUT, verify=context, auth=auth, transport=self.transport
        )
