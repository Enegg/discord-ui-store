from disnake import ui


# NOTE: as a result of supporting both custom_ids and urls, ui.Button has its .custom_id
# typed as str | None. This violates the interface of store.bind - it expects .custom_id
# to be solely str. The suggested workaround is to create a subclass like so:
class ActionButton(ui.Button[None]):
    @property
    def custom_id(self) -> str:
        custom_id = super().custom_id
        assert custom_id is not None
        return custom_id
