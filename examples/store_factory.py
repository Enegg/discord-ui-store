from functools import partial

import disnake

from ui_store import CallbackStore


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
