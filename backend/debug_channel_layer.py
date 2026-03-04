#!/usr/bin/env python
# pylint: disable=broad-exception-caught
"""
Debug the channel layer and group membership
"""
import os
import asyncio

import django

from channels.layers import get_channel_layer

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()


async def debug_channel_layer():
    """Debug the channel layer and group membership"""
    channel_layer = get_channel_layer()
    print(f"Channel layer type: {type(channel_layer)}")
    print(f"Channel layer backend: {channel_layer.__class__.__module__}")
    # Check if we can introspect groups (InMemoryChannelLayer doesn't support this well)
    try:
        # This will likely fail for InMemoryChannelLayer
        if hasattr(channel_layer, 'groups'):
            print(f"Groups: {channel_layer.groups}")
        else:
            print("Channel layer doesn't expose group information")
    except Exception as e:
        print(f"Error accessing groups: {e}")
    # Try to send a direct message to a specific channel
    try:
        # First, let's see what happens if we try to send to a non-existent channel
        print("\nTesting direct channel send...")
        await channel_layer.send("test_channel", {
            "type": "test_message",
            "text": "Direct channel test"
        })
        print("Direct channel send completed (no error means it was queued)")
    except Exception as e:
        print(f"Direct channel send failed: {e}")
    # Test group send
    try:
        print("\nTesting group send...")
        await channel_layer.group_send("test_group", {
            "type": "test_message",
            "text": "Group test"
        })
        print("Group send completed")
    except Exception as e:
        print(f"Group send failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_channel_layer())
