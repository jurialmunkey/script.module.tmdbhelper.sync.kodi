from collections import defaultdict
from jurialmunkey.ftools import cached_property
from tmdbhelper.lib.addon.logger import kodi_log
from tmdbhelper.lib.addon.tmdate import get_datetime_today
from tmdbhelper_sync_kodi.dates import kodi_date_to_zulu


class KodiSyncSnapshot:
    rewatch_enabled = True
    # Membership/watched state can exist without a corresponding Kodi date.
    unknown_date = '1970-01-01T00:00:00.000000Z'

    def __init__(self, library, item_type):
        self.library = library
        self.item_type = item_type

    @cached_property
    def items(self):
        return self.get_items()

    def get_items(self):
        if self.item_type == 'movie':
            return self.get_movies()
        return self.get_shows()

    def get_identified_items(self, media_type):
        items = []
        for item in self.library.get_items(media_type):
            tmdb_id = self.library.get_tmdb_id(item, media_type)
            if tmdb_id:
                items.append((item, tmdb_id))
            else:
                kodi_log(f'Kodi sync: no TMDb identity for {media_type} {item[media_type + "id"]}', 2)
        return items

    def get_movies(self):
        return [self.get_item(item, tmdb_id, 'movie')
                for item, tmdb_id in self.get_identified_items('movie')]

    @cached_property
    def episodes_by_show(self):
        return self.get_episodes_by_show()

    def get_episodes_by_show(self):
        episodes = defaultdict(list)
        for item in self.library.get_items('episode'):
            episodes[item['tvshowid']].append(item)
        return episodes

    def get_shows(self):
        return [record for show, tmdb_id in self.get_identified_items('tvshow')
                for record in self.get_show_items(show, tmdb_id)]

    def get_show_items(self, show, tmdb_id):
        episodes = [self.get_episode(item, tmdb_id) for item in self.episodes_by_show[show['tvshowid']]]
        seasons = self.get_seasons(episodes, show, tmdb_id)
        parent = self.get_item(show, tmdb_id, 'show')
        regular_episodes = [item for item in episodes if item['season_number'] > 0]
        self.configure_parent(parent, regular_episodes)
        return [parent, *seasons, *episodes]

    def get_seasons(self, episodes, show, tmdb_id):
        groups = defaultdict(list)
        for item in episodes:
            groups[item['season_number']].append(item)
        return [self.get_season(number, items, show, tmdb_id) for number, items in groups.items()]

    def get_season(self, number, episodes, show, tmdb_id):
        parent = self.get_item(show, tmdb_id, 'season')
        parent['season_number'] = number
        self.configure_parent(parent, episodes)
        if number == 0:
            parent['watched_episodes'] = 0
        return parent

    def get_item(self, item, tmdb_id, item_type):
        plays = item.get('playcount', 0)
        collected_at = kodi_date_to_zulu(item['dateadded']) or self.unknown_date
        return {
            'item_type': item_type, 'tmdb_id': tmdb_id,
            'title': item['title'], 'year': item.get('year'),
            'premiered': item.get('premiered') or item.get('firstaired'),
            'runtime': item.get('runtime', 0) // 60,
            'plays': plays,
            'last_watched_at': (kodi_date_to_zulu(item['lastplayed']) or self.unknown_date) if plays else None,
            'last_collected_at': collected_at, 'last_updated_at': collected_at,
            **self.get_playback(item),
        }

    def get_playback(self, item):
        resume = item.get('resume', {'position': 0, 'total': 0})
        if resume['position'] <= 0 or resume['total'] <= 0:
            return {}
        return {
            'progress': min(100, resume['position'] * 100 / resume['total']),
            'paused_at': kodi_date_to_zulu(item['lastplayed']) or self.unknown_date,
            'id': item['movieid'] if 'movieid' in item else item['episodeid'],
        }

    def get_episode(self, item, tmdb_id):
        record = self.get_item(item, tmdb_id, 'episode')
        record.update(season_number=item['season'], episode_number=item['episode'])
        return record

    def is_available_episode(self, item):
        premiered = item['premiered']
        return not premiered or premiered[:10] <= get_datetime_today().strftime('%Y-%m-%d')

    def configure_parent(self, parent, episodes):
        available = [item for item in episodes if self.is_available_episode(item)]
        watched = [item for item in episodes if item['plays'] > 0]
        parent['aired_episodes'] = len(available)
        parent['watched_episodes'] = len(watched)
        parent['plays'] = min((item['plays'] for item in available), default=0)
        parent['last_watched_at'] = max((item['last_watched_at'] for item in watched), default=None)
        parent['last_collected_at'] = min((item['last_collected_at'] for item in episodes), default=parent['last_collected_at'])
        parent['last_updated_at'] = max((item['last_updated_at'] for item in episodes), default=parent['last_updated_at'])
        self.configure_next_episode(parent, available, bool(watched or any(item.get('progress') for item in episodes)))

    def configure_next_episode(self, parent, episodes, started):
        episodes = sorted(
            (item for item in episodes if item['season_number'] > 0),
            key=self.get_episode_position)
        for item in episodes:
            if not item['plays']:
                item['upnext_episode_id'] = self.get_episode_id(item)
        if not started:
            return
        next_episode = self.get_next_episode(episodes)
        if next_episode is not None:
            parent['next_episode_id'] = self.get_episode_id(next_episode)
            parent['next_episode_aired_at'] = next_episode['premiered']

    @staticmethod
    def get_episode_position(item):
        return (item['season_number'], item['episode_number'])

    @staticmethod
    def get_episode_id(item):
        return f'tv.{item["tmdb_id"]}.{item["season_number"]}.{item["episode_number"]}'

    @staticmethod
    def get_episode_completed_at(item):
        if 'progress' in item:
            return item['paused_at'] if item['progress'] >= 80 else None
        return item['last_watched_at'] if item['plays'] > 0 else None

    def get_next_episode(self, episodes):
        if self.rewatch_enabled:
            return self.get_rewatch_next_episode(episodes)
        return next((item for item in episodes if not item['plays']), None)

    def get_rewatch_next_episode(self, episodes):
        latest = max(
            (item for item in episodes if self.get_episode_completed_at(item)),
            key=lambda item: (self.get_episode_completed_at(item), self.get_episode_position(item)),
            default=None)
        position = self.get_episode_position(latest) if latest is not None else (-1, -1)
        # All other completion dates precede the anchor, so later episodes are
        # eligible again even when they were watched during a previous viewing.
        return next((item for item in episodes if self.get_episode_position(item) > position), None)
