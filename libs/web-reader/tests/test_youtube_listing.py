
import pytest
import os
from web_reader.readers.youtube import list_channel_videos, resolve_channel_id

RUN_LIVE = os.getenv("RUN_WEB_READER_LIVE") == "1"

@pytest.mark.skipif(not RUN_LIVE, reason="set RUN_WEB_READER_LIVE=1 to run")
@pytest.mark.asyncio
async def test_youtube_handle_to_id():
    # Test handle resolution
    cid = await resolve_channel_id("@gooayepodcast")
    assert cid == "UCbmNph6atIoGqls4-fuXHkA"

@pytest.mark.skipif(not RUN_LIVE, reason="set RUN_WEB_READER_LIVE=1 to run")
@pytest.mark.asyncio
async def test_youtube_list_videos_via_handle():
    # Test listing via handle
    videos = await list_channel_videos("@gooayepodcast", limit=2)
    assert len(videos) > 0
    assert videos[0]["title"]
    assert "youtube.com/watch?v=" in videos[0]["url"]
