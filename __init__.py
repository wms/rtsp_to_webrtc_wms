"""RTSPtoWebRTC integration with an external RTSPToWebRTC Server.

WebRTC uses a direct communication from the client (e.g. a web browser) to a
camera device. Home Assistant acts as the signal path for initial set up,
passing through the client offer and returning a camera answer, then the client
and camera communicate directly.

However, not all cameras natively support WebRTC. This integration is a shim
for camera devices that support RTSP streams only, relying on an external
server RTSPToWebRTC that is a proxy. Home Assistant does not participate in
the offer/answer SDP protocol, other than as a signal path pass through.

Other integrations may use this integration with these steps:
- Check if this integration is loaded
- Call is_suported_stream_source for compatibility
- Call async_offer_for_stream_source to get back an answer for a client offer
"""

from __future__ import annotations

import logging

import async_timeout
from rtsp_to_webrtc.client import get_adaptive_client
from rtsp_to_webrtc.exceptions import ClientError, ResponseError
from rtsp_to_webrtc.interface import WebRTCClientInterface

from homeassistant.components import camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

DOMAIN = "rtsp_to_webrtc_wms"
DATA_SERVER_URL = "server_url"
DATA_UNSUB = "unsub"
TIMEOUT = 10


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RTSPtoWebRTC from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client: WebRTCClientInterface
    try:
        async with async_timeout.timeout(TIMEOUT):
            client = await get_adaptive_client(
                async_get_clientsession(hass), entry.data[DATA_SERVER_URL]
            )
    except ResponseError as err:
        raise ConfigEntryNotReady from err
    except (TimeoutError, ClientError) as err:
        raise ConfigEntryNotReady from err

    async def async_offer_for_stream_source(
        stream_source: str,
        offer_sdp: str,
        stream_id: str,
    ) -> str:
        """Handle the signal path for a WebRTC stream.

        This signal path is used to route the offer created by the client to the
        proxy server that translates a stream to WebRTC. The communication for
        the stream itself happens directly between the client and proxy.
        """
        try:
            async with async_timeout.timeout(TIMEOUT):
                """ wms: call client.webrtc directly, which skips attempting to create/update a stream.
                
                This prevents existing streams being silently dropped.

                return await client.offer_stream_id(stream_id, offer_sdp, stream_source)
                """
                return await client.webrtc(stream_id, "0", offer_sdp)
        except TimeoutError as err:
            raise HomeAssistantError("Timeout talking to RTSPtoWebRTC server") from err
        except ClientError as err:
            raise HomeAssistantError(str(err)) from err

    entry.async_on_unload(
        camera.async_register_rtsp_to_web_rtc_provider(
            hass, DOMAIN, async_offer_for_stream_source
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
