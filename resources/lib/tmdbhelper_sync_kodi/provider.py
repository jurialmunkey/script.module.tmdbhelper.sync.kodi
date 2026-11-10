from jurialmunkey.ftools import cached_property
from jurialmunkey.window import get_property
from tmdbhelper.lib.addon.consts import KODI_LIBRARY_LAST_UPDATED
from tmdbhelper.lib.sync.providers.base import SyncProvider
from tmdbhelper_sync_kodi.library import KodiLibraryClient
from tmdbhelper_sync_kodi.settings import KodiSettings
from tmdbhelper_sync_kodi.sync import synctype, datasync
from tmdbhelper_sync_kodi.actions.basic import ItemWatched, ItemUnwatched
from tmdbhelper_sync_kodi.actions.progress import ItemProgress
from tmdbhelper_sync_kodi.actions.watchlist import ItemWatchlist
from tmdbhelper_sync_kodi.scrobbler import ProviderScrobbler
from tmdbhelper_sync_kodi.sync.watchlist import SyncWatchlist
from tmdbhelper_sync_kodi.watchlist.database import WatchlistDatabase
from tmdbhelper_sync_kodi.history.database import HistoryDatabase


class Provider(SyncProvider):
    interface_version = 4
    provider_id = 'kodi'
    display_name = 'Kodi'
    sync_classes = {
        'SyncCollection': synctype.SyncCollection,
        'SyncWatched': synctype.SyncWatched,
        'SyncWatchlist': SyncWatchlist,
        'SyncPlayback': synctype.SyncPlayback,
        'SyncAiredEpisodes': synctype.SyncAiredEpisodes,
        'SyncNextEpisodes': synctype.SyncNextEpisodes,
        'SyncAllNextEpisodes': synctype.SyncAllNextEpisodes,
    }
    action_classes = {
        'watched': ItemWatched,
        'unwatched': ItemUnwatched,
        'progress': ItemProgress,
        'watchlist': ItemWatchlist,
    }
    getter_classes = {
        'movies_to_watch': datasync.KodiSyncDataGetterMoviesToWatch,
        'shows_to_watch': datasync.KodiSyncDataGetterShowsToWatch,
        'shows_in_progress': datasync.KodiSyncDataGetterShowsInProgress,
    }
    scrobbler_class = ProviderScrobbler

    @cached_property
    def settings(self):
        return self.get_settings()

    def get_settings(self):
        return KodiSettings()

    @cached_property
    def library(self):
        return self.get_library()

    def get_library(self):
        return KodiLibraryClient()

    @cached_property
    def watchlist(self):
        return self.get_watchlist()

    def get_watchlist(self):
        return WatchlistDatabase()

    @cached_property
    def history(self):
        return self.get_history()

    def get_history(self):
        return HistoryDatabase()

    def is_authorized(self):
        return True

    def get_last_activities(self):
        timestamp = get_property(KODI_LIBRARY_LAST_UPDATED)
        return {
            item_type: {
                key: timestamp for key in ('collected_at', 'watched_at', 'paused_at')
            } for item_type in ('movies', 'episodes')
        }
