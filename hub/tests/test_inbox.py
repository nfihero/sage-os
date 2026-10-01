import asyncio

import pytest

from sage_os_hub.inbox import Inbox, future_resolver


def make():
    published, events = [], []
    return Inbox(published.append, lambda *a, **k: events.append(a)), published, events


def test_resolve_delivers_choice_and_note():
    async def go():
        inbox, published, events = make()
        fut = asyncio.get_running_loop().create_future()
        iid = inbox.add(source="claude", title="Bash", detail="pytest", choices=["allow_once", "deny"],
                        resolver=future_resolver(fut))
        assert inbox.items()[0]["id"] == iid
        with pytest.raises(ValueError):
            await inbox.resolve(iid, "allow_always")
        await inbox.resolve(iid, "deny", "not now")
        assert fut.result() == ("deny", "not now") and inbox.items() == []
        assert [e[2] for e in events] == ["approval.requested", "approval.resolved"]
    asyncio.run(go())


def test_keyed_items_are_idempotent_and_droppable():
    inbox, _, _ = make()

    async def noop(c, n):
        pass
    a = inbox.add(source="kanban", title="t", detail="d", choices=["reply_unblock"], resolver=noop, key="kanban:t1")
    b = inbox.add(source="kanban", title="t", detail="d", choices=["reply_unblock"], resolver=noop, key="kanban:t1")
    assert a == b and len(inbox.items()) == 1
    inbox.drop("kanban:t1")
    assert inbox.items() == []


def test_failed_resolver_keeps_item():
    async def go():
        inbox, _, _ = make()

        async def boom(c, n):
            raise ValueError("write an answer first")
        iid = inbox.add(source="kanban", title="t", detail="d", choices=["reply_only"], resolver=boom)
        with pytest.raises(ValueError):
            await inbox.resolve(iid, "reply_only", "")
        assert len(inbox.items()) == 1
    asyncio.run(go())
