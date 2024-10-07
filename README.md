discord-ui-store
================
An extension to disnake-like libraries providing an alternative to `.ui.View`s.

Key features
------------
- Separation of concerns - `CallbackStore` manages callback registration & dispatching;<br>
  how the components interact & are sent is left out to the user
- No inheritance, no metaclass hacks
- Integrates with [disnake](https://github.com/DisnakeDev/disnake)

But what does "disnake-like" mean?
----------------------------------
So long as your API wrapper of choice supports:
1. sending components without a view (`.send(components=[...])`)
2. a way to listen for a specific event (`Client.wait_for`)
3. the event mentioned above returns an object having `.data.custom_id`

The extension should be interoperable with your wrapper.

This is achieved by leveraging structural subtyping, rather than importing nominal types
from a concrete wrapper.

In practice, at the time being *disnake* is the only library supporting that interface,
as it is the only wrapper which, among other things, provides a way to send components
in a message beyond views.

Installing
----------
**Python 3.9 or higher is required**

```sh
# Linux/macOS
python3 -m pip install -U git+https://github.com/Enegg/discord-ui-store

# Windows
py -3 -m pip install -U git+https://github.com/Enegg/discord-ui-store
```

Example
-------
```py
from functools import partial

import disnake
from disnake import Event, ui
from disnake.ext import commands
from ui_store import CallbackStore


@commands.slash_command()
async def command(inter: disnake.CommandInteraction) -> None:
    listener = partial(inter.bot.wait_for, Event.message_interaction)
    store = CallbackStore(listener)

    @store.bind(ui.Button(label="Hello", custom_id=store.make_id()))
    async def my_button(inter: disnake.MessageInteraction) -> None:
        my_button.disabled = True
        store.stop()
        await inter.response.edit_message("World", components=layout)

    # woo, freedom of layout
    layout = [[my_button]]
    await inter.response.send_message(components=layout)

    if await store.listen():
        await inter.edit_original_response(components=None)
```
It's recommended that you create a [factory function](/examples/store_factory.py)
which creates an instance of `CallbackStore` tailored to your and your library's needs.

See more examples [here](/examples/).