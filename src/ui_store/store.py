import os
from collections import abc
from typing import ClassVar, Final, Generic, Protocol
from typing_extensions import TypeAlias, TypeVar

import anyio
import anyio.lowlevel
import attrs

__all__ = ("CallbackStore",)


class HasCustomID(Protocol):
    @property
    def custom_id(self) -> str: ...


class HasData(Protocol):
    @property
    def data(self) -> HasCustomID: ...


T = TypeVar("T", infer_variance=True)
ItemT = TypeVar("ItemT", bound=HasCustomID, infer_variance=True)
InterT = TypeVar("InterT", bound=HasData, infer_variance=True)
InteractionCallback: TypeAlias = abc.Callable[[InterT], abc.Awaitable[T]]
Decorator: TypeAlias = abc.Callable[[InteractionCallback[InterT, None]], T]


# the libraries expect `check=` to be passed via keyword
class InteractionListener(Protocol[InterT]):
    async def __call__(self, event: str, /, *, check: abc.Callable[[InterT], bool]) -> InterT: ...


def random_str() -> str:
    return os.urandom(8).hex()


@attrs.define
class CallbackStore(Generic[InterT]):
    """Registry & dispatch for callbacks of UI components.

    .. note::
        It is not intended that you change the `.custom_id`s of components which callbacks
        have been bound to the store. Doing so will stop it from recognizing the interactions.
        As such, it is not viable to embed mutable state within the ID.
    """

    event_name: ClassVar[str] = "message_interaction"

    id: Final[str] = attrs.field(factory=random_str)
    """Unique ID of this object."""

    _callbacks: dict[str, InteractionCallback[InterT, None]] = attrs.field(factory=dict, init=False)
    """Mapping of `custom_id`s to callbacks of components."""
    _cs: anyio.CancelScope = attrs.field(factory=anyio.CancelScope, init=False)
    """CancelScope stopping the main loop by timeout or .stop call."""
    _id_counter: int = attrs.field(default=0, init=False)
    """Counter for component `custom_id` generation."""

    @staticmethod
    async def default_check(inter: HasData, /) -> bool:
        """Interaction check which allows all interactions."""
        await anyio.lowlevel.checkpoint()
        return True

    async def listen(
        self,
        listener: InteractionListener[InterT],
        *,
        check: InteractionCallback[InterT, bool] = default_check,
        timeout: int = 180,  # noqa: ASYNC109
    ) -> bool:
        """Run the main loop until stopped.

        Example
        -------
        ```
        layout = make_layout(store)  # create components and bind them to the store
        await inter.response.send_message(components=layout)

        if await store.listen(client.wait_for):
            await inter.edit_original_response(components=None)
        ```

        Parameters
        ----------
        listener:
            Async callable which listens for component interactions.
        check: optional
            Check whether an interaction should be propagated to the callbacks.
        timeout: optional
            Number of seconds since last interaction until the loop stops.

        Returns
        -------
        bool
            `True` on timeout, `False` after `.stop`.
        """
        self._cs.deadline = anyio.current_time() + timeout

        while True:
            with self._cs:
                inter = await listener(
                    self.event_name, check=lambda inter: inter.data.custom_id in self._callbacks
                )

            if self._cs.cancelled_caught:
                return not self._cs.cancel_called

            if not await check(inter):
                continue

            await self._callbacks[inter.data.custom_id](inter)
            # don't reset the deadline for interactions rejected by the check
            self._cs.deadline = anyio.current_time() + timeout

    def stop(self) -> None:
        """Stop the loop and signal to `.listen` method to return."""
        self._cs.cancel()

    def bind(self, component: ItemT, /) -> Decorator[InterT, ItemT]:
        """Register a callback for the component.

        Assigns the component under the decorated function's name.

        Example
        -------
        ```
        from MyDiscordLib import MessageInteraction, ui

        @store.bind(ui.Button(..., custom_id=store.make_id()))
        async def my_button(inter: MessageInteraction) -> None:
            my_button.disabled = True
            await inter.response.edit_message(components=[[my_button]])
        ```
        """

        def catch_callback(func: InteractionCallback[InterT, None], /) -> ItemT:
            self._callbacks[component.custom_id] = func
            return component

        return catch_callback

    def make_id(self, *parts: str) -> str:
        """Create a custom ID with a header unique to this store.

        See `.bind` for usage.
        """
        if not parts:
            custom_id = f"{self.id}:{self._id_counter}"
            self._id_counter += 1
            return custom_id

        return ":".join((self.id, *parts))

    def strip_id(self, component: HasCustomID, /) -> str:
        """Remove the header from the custom ID."""
        return component.custom_id.removeprefix(self.id + ":")
