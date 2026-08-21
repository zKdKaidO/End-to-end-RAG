import asyncio

import pytest

from app.api.routes.answer import ClientDisconnected, guarded_upstream


@pytest.mark.asyncio
async def test_client_disconnect_cancels_and_closes_upstream_without_done():
    state = {"closed": False, "polls": 0}
    never = asyncio.Event()

    async def upstream():
        try:
            await never.wait()
            yield "done", object()
        finally:
            state["closed"] = True

    async def disconnected():
        state["polls"] += 1
        return state["polls"] >= 2

    with pytest.raises(ClientDisconnected):
        _ = [item async for item in guarded_upstream(upstream(), disconnected)]
    assert state["closed"] is True
