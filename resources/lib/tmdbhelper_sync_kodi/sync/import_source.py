from jurialmunkey.ftools import cached_property
from tmdbhelper.lib.sync.datasync import SyncData


class ImportSourceError(RuntimeError):
    pass


class ImportSource:
    """Read full, provider-mapped snapshots without updating the selected sync cache."""

    def __init__(self, provider, dialog):
        self.provider = provider
        self.dialog = dialog

    @cached_property
    def syncdata(self):
        return self.get_syncdata()

    def get_syncdata(self):
        return SyncData()

    def get_records(self, sync_type, item_type):
        sync_class = self.provider.get_sync_class(sync_type)
        if sync_class is None:
            return {}
        datatype = sync_class(self.syncdata, item_type, self.provider)
        # A manual import needs a full response, independent of normal sync activity.
        datatype.timestamp = None
        datatype.dialog_progress_bg = self.dialog
        meta = datatype.get_response_sync(*datatype.sync_args, **datatype.sync_kwgs)
        if meta is None:
            raise ImportSourceError(f'{self.provider.display_name}: {sync_type} {item_type}')
        mapped = datatype.get_syncitem(meta)
        return {item_id: dict(zip(mapped.table_keys, values)) for item_id, values in mapped.data.items()}

    def merge_records(self, records, items):
        for item_id, item in items.items():
            # Show/season rows summarize episodes; they are not individual plays.
            if item['item_type'] not in ('movie', 'episode'):
                continue
            records.setdefault(item_id, {}).update(item)

    def get_items(self):
        records = {}
        for sync_type, item_type in (
                ('SyncWatched', 'movie'), ('SyncWatched', 'show'),
                ('SyncPlayback', 'movie'), ('SyncPlayback', 'show')):
            self.merge_records(records, self.get_records(sync_type, item_type))
        return list(records.values())
