discord-ui-store
================
An extension library providing an alternative to `.ui.View`s.<br>
Works with any discord.py fork which supports sending individual components.

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
import asyncio

import disnake
from disnake import ui
from disnake.ext import commands
from ui_store import CallbackStore


@commands.slash_command()
async def command(inter: disnake.CommandInteraction) -> None:
    store = CallbackStore()

    @store.bind(ui.Button(label="Hello", custom_id=store.make_id()))
    async def my_button(inter: disnake.MessageInteraction) -> None:
        my_button.disabled = True
        store.stop()
        await inter.response.edit_message("World", components=layout)

    layout = [[my_button]]
    await inter.response.send_message(components=layout)

    try:
        async with asyncio.timeout(60):
            await store.listen(inter.bot.wait_for)

    except TimeoutError:
        await inter.edit_original_response(components=None)
```