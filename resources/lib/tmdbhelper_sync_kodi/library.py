from jurialmunkey.ftools import cached_property
from jurialmunkey.parser import try_int
from tmdbhelper.lib.api.kodi.rpc import get_jsonrpc


class KodiLibraryError(RuntimeError):
    pass


class KodiLibraryClient:
    page_size = 1000
    method_types = {'movie': 'Movie', 'tvshow': 'TVShow', 'episode': 'Episode'}
    item_properties = {
        'movie': ('title', 'year', 'uniqueid', 'imdbnumber', 'premiered', 'dateadded',
                  'playcount', 'lastplayed', 'resume', 'runtime', 'file'),
        'tvshow': ('title', 'year', 'uniqueid', 'imdbnumber', 'premiered', 'dateadded'),
        'episode': ('title', 'season', 'episode', 'tvshowid', 'firstaired', 'dateadded',
                    'playcount', 'lastplayed', 'resume', 'runtime', 'file'),
    }

    @cached_property
    def query_database(self):
        return self.get_query_database()

    def get_query_database(self):
        from tmdbhelper.lib.query.database.database import FindQueriesDatabase
        return FindQueriesDatabase()

    def request(self, method, params=None):
        response = get_jsonrpc(method, params)
        try:
            return response['result']
        except KeyError:
            raise KodiLibraryError(f'{method}: {response.get("error", "Missing result")}')

    def get_items(self, media_type, **params):
        method = f'VideoLibrary.Get{self.method_types[media_type]}s'
        params['properties'] = list(self.item_properties[media_type])
        items = []
        start = 0
        while True:
            params['limits'] = {'start': start, 'end': start + self.page_size}
            result = self.request(method, params)
            page = result.get(f'{media_type}s', [])
            items.extend(page)
            limits = result['limits']
            if len(page) != limits['end'] - limits['start']:
                raise KodiLibraryError(f'{method}: incomplete library snapshot')
            if limits['end'] >= limits['total']:
                return items
            if limits['end'] <= start:
                raise KodiLibraryError(f'{method}: incomplete library snapshot')
            start = limits['end']

    def get_tmdb_id(self, item, media_type):
        unique_ids = item.get('uniqueid') or {}
        tmdb_id = try_int(unique_ids.get('tmdb'))
        if tmdb_id:
            return tmdb_id
        imdb_id = unique_ids.get('imdb') or item.get('imdbnumber') or ''
        imdb_id = imdb_id if isinstance(imdb_id, str) and imdb_id.startswith('tt') else None
        tvdb_id = unique_ids.get('tvdb')
        if not imdb_id and not tvdb_id:
            return None
        return self.query_database.get_tmdb_id(
            tmdb_type='movie' if media_type == 'movie' else 'tv',
            imdb_id=imdb_id, tvdb_id=tvdb_id)

    def get_targets(self, tmdb_type, tmdb_id, season=None, episode=None):
        media_type = 'movie' if tmdb_type == 'movie' else 'tvshow'
        parents = [item for item in self.get_items(media_type)
                   if str(self.get_tmdb_id(item, media_type)) == str(tmdb_id)]
        if media_type == 'movie':
            return parents
        return [item for parent in parents for item in self.get_show_targets(parent, season, episode)]

    def get_show_targets(self, show, season, episode):
        params = {'tvshowid': show['tvshowid']}
        if season is not None:
            params['season'] = try_int(season)
        return [item for item in self.get_items('episode', **params)
                if episode is None or item['episode'] == try_int(episode)]

    def get_details(self, item, media_type):
        result = self.request(f'VideoLibrary.Get{self.method_types[media_type]}Details', {
            f'{media_type}id': item[f'{media_type}id'],
            'properties': list(self.item_properties[media_type]),
        })
        return result[f'{media_type}details']

    def set_details(self, item, media_type, **values):
        result = self.request(f'VideoLibrary.Set{self.method_types[media_type]}Details', {
            f'{media_type}id': item[f'{media_type}id'], **values,
        })
        if result != 'OK':
            raise KodiLibraryError(f'Updating {media_type} returned {result!r}')
        return True

    def get_playing_item(self):
        players = self.request('Player.GetActivePlayers')
        player = next((item for item in players if item['type'] == 'video'), None)
        if player is None:
            return {}
        return self.request('Player.GetItem', {
            'playerid': player['playerid'], 'properties': ['file'],
        })['item']

    def is_native_playback(self, item, media_type, playing_item):
        if playing_item.get('type') == media_type and playing_item.get('id') == item[f'{media_type}id']:
            return True
        return bool(item['file'] and item['file'] == playing_item.get('file'))
