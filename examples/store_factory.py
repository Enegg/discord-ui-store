from functools import partial

import disnake

from ui_store import CallbackStore

# It might get annoying to write boilerplate code for defining a listener and/or a check function.
# It's an unfortunate consequence of not binding the implementation to any specific wrapper.
# However, it should be trivial to wrap that into a factory function:

def callback_store(inter: disnake.CommandInteraction) -> CallbackStore[disnake.MessageInteraction]:
    # reject interactions from users other than the command invoker
    async def check(interaction: disnake.MessageInteraction, /) -> bool:
        if interaction.author == inter.author:
            return True

        msg = "You cannot interact with that!"
        await interaction.response.send_message(msg, ephemeral=True)
        return False

    return CallbackStore(
        listener=partial(inter.bot.wait_for, disnake.Event.message_interaction),
        check=check,
    )
