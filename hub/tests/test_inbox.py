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


def test_requests_come_first_and_proposals_read_oldest_first():
    from sage_os_hub.inbox import Inbox

    async def noop(choice, note):
        pass
    box = Inbox(lambda m: None, lambda *a, **k: None)
    box.add(source="bookshelf", title="ch 2", detail="", choices=["approve"], resolver=noop, key="b2", created=200)
    box.add(source="bookshelf", title="ch 1", detail="", choices=["approve"], resolver=noop, key="b1", created=100)
    box.add(source="claude", title="old ask", detail="", choices=["deny"], resolver=noop, key="c1", created=50)
    box.add(source="claude", title="new ask", detail="", choices=["deny"], resolver=noop, key="c2", created=300)
    assert [i["title"] for i in box.items()] == ["new ask", "old ask", "ch 1", "ch 2"]


def test_digest_cards_name_the_book_and_chapter():
    from sage_os_hub.app import proposal_card
    p = {"agent": "digest:file:gemma-4-12b", "changes": [{}] * 50,
         "summary": "Intermediate_Accounting__18th_Edition_Kieso_--_Wiley_--_96f0ad: Chapter 7: Valuation of Inventories: "
                    "A Cost-Basis Approach (part 1 of 3): 50 notes from 30 sections, 180/180 listed concepts covered"}
    title, detail = proposal_card(p)
    assert title == "Intermediate Accounting 18th Edition Kieso · Chapter 7: Valuation of Inventories: A Cost-Basis Approach (part 1 of 3)"
    assert detail.startswith("50 notes from 30 sections") and "gemma-4-12b" in detail
    other = proposal_card({"agent": "claude:cs_x", "changes": [{}], "summary": "a note"})
    assert other == ("claude:cs_x proposes 1 change to the Bookshelf", "a note")
