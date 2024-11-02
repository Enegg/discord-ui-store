from collections import abc
from typing import Any, cast as type_cast
from typing_extensions import assert_type

from disnake import MessageInteraction, ui

from ui_store import CallbackStore

store = type_cast(CallbackStore[MessageInteraction], None)


@store.bind(ui.MentionableSelect(custom_id=store.make_id()))
async def mentionable(inter: MessageInteraction) -> None:
    mentionable.disabled = True


@store.bind_many(
    ui.StringSelect(custom_id=store.make_id()),
    ui.UserSelect(custom_id=store.make_id()),
    ui.MentionableSelect(custom_id=store.make_id()),
)
async def selects(index: int, inter: MessageInteraction) -> None:
    selects[index].disabled = True


assert_type(mentionable, ui.MentionableSelect[None])
_1: abc.Sequence[ui.BaseSelect[Any, Any, None]] = selects
