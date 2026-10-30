from tmdbhelper.lib.script.sync.progress import ItemProgress as BasicItemProgress
from tmdbhelper_sync_kodi.actions.item import ItemSync


class ItemProgress(ItemSync, BasicItemProgress):
    sync_types = ('SyncPlayback',)
    show_sync_types = ('SyncNextEpisodes', 'SyncAllNextEpisodes')
    allow_shows = False

    def update_history_item(self, item):
        return self.history.remove_progress(item)

    def update_item(self, item):
        return self.library.set_details(item, self.media_type, resume={'position': 0, 'total': 0})
