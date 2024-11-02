import os
from collections import abc
from datetime import timedelta
from typing import Final, Generic, Protocol, Union
from typing_extensions import ParamSpec, TypeAlias, TypeVar

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
P = ParamSpec("P")
ItemT = TypeVar("ItemT", bound=HasCustomID, infer_variance=True)
InterT = TypeVar("InterT", bound=HasData, infer_variance=True)
AsyncFunc: TypeAlias = abc.Callable[P, abc.Awaitable[T]]
Decorator: TypeAlias = abc.Callable[[AsyncFunc[P, None]], T]


# we pass `check` as keyword
class InteractionListener(Protocol[InterT]):
    async def __call__(self, *, check: abc.Callable[[InterT], bool]) -> InterT: ...


class FloatAddable(Protocol):
    def __radd__(self, other: float, /) -> float: ...


Seconds: TypeAlias = Union[int, float, timedelta, FloatAddable]


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

    @staticmethod
    async def default_check(inter: HasData, /) -> bool:
        """Interaction check which allows all interactions."""
        await anyio.lowlevel.checkpoint()
        return True

    listener: InteractionListener[InterT]
    """Async callable which listens for component interactions."""
    check: AsyncFunc[[InterT], bool] = default_check
    """Check whether an interaction should be propagated to the callbacks."""
    id: Final[str] = attrs.field(factory=random_str, kw_only=True)
    """Unique ID of this object."""

    _callbacks: dict[str, AsyncFunc[[InterT], None]] = attrs.field(
        factory=dict, init=False, eq=False
    )
    """Mapping of `custom_id`s to callbacks of components."""
    _cs: anyio.CancelScope = attrs.field(factory=anyio.CancelScope, init=False, eq=False)
    """`CancelScope` stopping the main loop by timeout or .stop call."""
    _id_counter: int = attrs.field(default=0, init=False, eq=False)
    """Counter for component `custom_id` generation."""

    async def listen(self, *, timeout: Seconds = 180) -> bool:  # noqa: ASYNC109
        """Run the main loop until stopped.

        Example
        -------
        ```
        layout = make_layout(store)  # create components and bind them to the store
        await inter.response.send_message(components=layout)

        if await store.listen():
            await inter.edit_original_response(components=None)
        ```

        Parameters
        ----------
        timeout: optional
            Number of seconds since last interaction until the loop stops.

        Returns
        -------
        bool
            `True` on timeout, `False` after `.stop`.
        """
        if isinstance(timeout, timedelta):
            timeout = timeout.total_seconds()

        self._cs.deadline = anyio.current_time() + timeout
        shield_interaction_responses = anyio.CancelScope(shield=True)

        def check_id(inter: HasData, /) -> bool:
            return inter.data.custom_id in self._callbacks

        while True:
            with self._cs:
                inter = await self.listener(check=check_id)

            # anyio.fail_after does something similar
            if self._cs.cancelled_caught:
                return not self._cs.cancel_called

            with shield_interaction_responses:
                if not await self.check(inter):
                    continue

                await self._callbacks[inter.data.custom_id](inter)
                # don't reset the deadline for interactions rejected by the check
                self._cs.deadline = anyio.current_time() + timeout

    def stop(self) -> None:
        """Stop the loop and signal to `.listen` method to return."""
        self._cs.cancel()

    def bind(self, component: ItemT, /) -> Decorator[[InterT], ItemT]:
        """Register a callback for the component.

        Assigns the component under the decorated function's name.

        Example
        -------
        ```
        @store.bind(ui.Button(..., custom_id=store.make_id()))
        async def my_button(inter: MessageInteraction) -> None:
            my_button.disabled = True
            await inter.response.edit_message(components=[[my_button]])
        # my_button is now the Button passed to the decorator
        ```
        """

        def catch_callback(func: AsyncFunc[[InterT], None], /) -> ItemT:
            self._callbacks[component.custom_id] = func
            return component

        return catch_callback

    # this could be a nice use case for TypeVarTuples if they could be constrained...
    def bind_many(self, *components: ItemT) -> Decorator[[int, InterT], tuple[ItemT, ...]]:
        """Register a callback shared by multiple components.

        The callback receives the index of a component that invoked it as the first param.

        Assigns a tuple of the components under the decorated function's name.

        Example
        -------
        ```
        @store.bind_many(
            ui.Button(..., custom_id=store.make_id()),
            ui.Button(..., custom_id=store.make_id())
        )
        async def buttons(index: int, inter: MessageInteraction) -> None:
            button = buttons[index]
            ...
        # buttons is now a tuple of components passed to the decorator
        """
        from functools import partial

        def catch_callback(func: AsyncFunc[[int, InterT], None], /) -> tuple[ItemT, ...]:
            for i, component in enumerate(components):
                self._callbacks[component.custom_id] = partial(func, i)
            return components

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
