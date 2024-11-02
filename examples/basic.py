from collections import abc
from functools import partial

import disnake
from disnake import ButtonStyle, Event, MessageInteraction, ui
from disnake.ext import commands

from ui_store import CallbackStore

from .store_factory import callback_store
from .utils import ActionButton


# for simple use cases, you can do the component binding directly in a command's body
@commands.slash_command()
async def basic_command(inter: disnake.CommandInteraction) -> None:
    store = CallbackStore(partial(inter.bot.wait_for, Event.message_interaction))

    @store.bind(ui.StringSelect(options=["Hi", "World"], custom_id=store.make_id()))
    async def my_select(inter: MessageInteraction) -> None:
        my_select.disabled = True
        store.stop()
        assert inter.values is not None
        await inter.response.edit_message(inter.values[0], components=layout)

    layout = [[my_select]]
    await inter.response.send_message("Hello", components=layout)

    if await store.listen():
        await inter.edit_original_response(components=None)


# As the number & complexity of relations between your components grows, you can extract the
# component/callback defining code into a separate function. This serves two purposes:
# - reduces the number of local variables that you need to keep track of,
# - makes the store reusable.
def my_view(store: CallbackStore[MessageInteraction]) -> ui.Components[ui.MessageUIComponent]:
    @store.bind(ActionButton(label="Button 1", custom_id=store.make_id()))
    async def button_1(inter: MessageInteraction) -> None:
        button_1.disabled = True
        button_2.disabled = False
        await inter.response.edit_message(components=layout)

    @store.bind(ActionButton(label="Button 2", custom_id=store.make_id()))
    async def button_2(inter: MessageInteraction) -> None:
        button_1.disabled = False
        button_2.disabled = True
        await inter.response.edit_message(components=layout)

    @store.bind(ActionButton(label="Quit", style=ButtonStyle.red, custom_id=store.make_id()))
    async def quit_button(inter: MessageInteraction) -> None:
        store.stop()
        await inter.response.defer()

    url_button = ui.Button(
        label="Hi Rick", url="https://www.youtube.com/watch?v=dQw4w9WgXcQ&pp=ygUJcmljayByb2xs"
    )

    # this is where your freedom of layout comes from:
    # you can use a list with all its benefits of slicing, appending & other mutation methods,
    # you can use a custom paginator object storing pages of components - the choice is yours!
    layout = [[button_1, button_2, quit_button], [url_button]]
    return layout  # noqa: RET504


@commands.slash_command()
async def intermediate_command(inter: disnake.CommandInteraction) -> None:
    store = callback_store(inter)
    layout = my_view(store)
    await inter.response.send_message(components=layout)
    await store.listen()
    await inter.edit_original_response(components=None)


# If the amount of variables outgrows the locals of a function, you can create a class.
class MyView:
    page: int
    store: CallbackStore[MessageInteraction]
    embeds: abc.Sequence[disnake.Embed]
    layout: ui.Components[ui.MessageUIComponent]

    def __init__(
        self, store: CallbackStore[MessageInteraction], embeds: abc.Sequence[disnake.Embed]
    ) -> None:
        self.page = 0
        self.store = store
        self.embeds = embeds
        self.init_components(store)

    @property
    def current_embed(self) -> disnake.Embed:
        return self.embeds[self.page]

    def init_components(self, store: CallbackStore[MessageInteraction]) -> None:
        def update_buttons() -> None:
            prev_button.disabled = self.page == 0
            next_button.disabled = self.page == len(self.embeds) - 1

        @store.bind(ActionButton(label="🡸", disabled=True, custom_id=store.make_id()))
        async def prev_button(inter: MessageInteraction) -> None:
            self.page -= 1
            update_buttons()
            await inter.response.edit_message(embed=self.current_embed, components=layout)

        @store.bind(
            ActionButton(label="🡺", disabled=len(self.embeds) <= 1, custom_id=store.make_id())
        )
        async def next_button(inter: MessageInteraction) -> None:
            self.page += 1
            update_buttons()
            await inter.response.edit_message(embed=self.current_embed, components=layout)

        layout = [[prev_button, next_button]]
        self.layout = layout


@commands.slash_command()
async def advanced_command(inter: disnake.CommandInteraction) -> None:
    store = callback_store(inter)
    embeds = [disnake.Embed(title="Hello", description="World")]
    view = MyView(store, embeds)
    await inter.response.send_message(embed=view.current_embed, components=view.layout)
    await store.listen()
    await inter.edit_original_response(components=None)
