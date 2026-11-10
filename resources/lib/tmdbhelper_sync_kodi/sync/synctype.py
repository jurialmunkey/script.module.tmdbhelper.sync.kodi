from jurialmunkey.ftools import cached_property
from tmdbhelper.lib.addon.logger import kodi_log
from tmdbhelper_sync_kodi.library import KodiLibraryError
from tmdbhelper_sync_kodi.sync.datatype import KodiDataType
from tmdbhelper_sync_kodi.sync.history import KodiHistoryDataType
from tmdbhelper_sync_kodi.sync.snapshot import KodiSyncSnapshot


class SyncCollection(KodiDataType):
    keys = ('last_collected_at', 'last_updated_at')
    key_prefix = 'collection'
    method = 'library/collection'
    last_activities_key = 'collected_at'


class SyncWatched(KodiHistoryDataType):
    keys = ('plays', 'last_watched_at', 'watched_episodes')
    method = 'library/watched'
    last_activities_key = 'watched_at'


class SyncPlayback(KodiHistoryDataType):
    keys = ('progress', 'paused_at', 'id')
    key_prefix = 'playback'
    method = 'library/playback'
    last_activities_key = 'paused_at'


class SyncAiredEpisodes(KodiDataType):
    keys = ('aired_episodes',)
    method = 'library/episodes'
    last_activities_key = 'collected_at'


class SyncNextEpisodes(KodiDataType):
    keys = ('next_episode_id', 'next_episode_aired_at')
    method = 'library/next'
    last_activities_key = 'watched_at'

    @cached_property
    def rewatch_enabled(self):
        return self.get_rewatch_enabled()

    def get_rewatch_enabled(self):
        return self.provider.settings.rewatch_enabled

    @property
    def rewatch_configuration(self):
        return str(int(self.rewatch_enabled))

    @property
    def rewatch_activity_method(self):
        return f'{self.cache_method}.rewatch'

    @cached_property
    def is_expired(self):
        return self.get_is_expired()

    def get_is_expired(self):
        configuration = self.cache.get_activity(self.item_type, self.rewatch_activity_method)
        return configuration != self.rewatch_configuration or super().is_expired

    def store_last_activity(self):
        super().store_last_activity()
        self.cache.set_activity(
            self.item_type,
            self.rewatch_activity_method,
            self.rewatch_configuration,
            self.sync_expiry,
        )

    def get_response_sync(self, *args, **kwargs):
        try:
            snapshot = KodiSyncSnapshot(self.provider.library, self.item_type)
            snapshot.rewatch_enabled = self.rewatch_enabled
            return snapshot.items
        except KodiLibraryError as exc:
            kodi_log(f'Kodi sync: {exc}', 1)
            return


class SyncAllNextEpisodes(KodiDataType):
    keys = ('upnext_episode_id',)
    method = 'library/upnext'
    last_activities_key = 'watched_at'
