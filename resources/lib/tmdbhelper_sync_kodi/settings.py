from sqlite3 import Error as DatabaseError
from xbmcaddon import Addon
from xbmcgui import Dialog
from tmdbhelper.lib.addon.dialog import DialogProgressSyncBG
from tmdbhelper.lib.addon.logger import kodi_log
from tmdbhelper.lib.files.locker import mutexlock
from tmdbhelper_sync_kodi.library import KodiLibraryError
from tmdbhelper_sync_kodi.sync.import_history import HistoryImporter
from tmdbhelper_sync_kodi.sync.import_source import ImportSource, ImportSourceError


class KodiSettings:
    addon_id = 'script.module.tmdbhelper.sync.kodi'

    def __init__(self):
        self.addon = Addon(self.addon_id)

    @property
    def rewatch_enabled(self):
        return self.addon.getSettingBool('rewatch_enabled')


class ImportHistorySettings:
    heading = 'Kodi: Import watched/progress'
    mutex_lockname = 'tmdbhelper_sync_kodi.import_history'

    def __init__(self, registry):
        self.registry = registry
        self.addon = Addon('script.module.tmdbhelper.sync.kodi')

    def get_localized(self, string_id):
        return self.addon.getLocalizedString(string_id)

    def get_providers(self):
        return sorted(
            (provider for provider in self.registry.get_capable_providers('watched')
             if provider.provider_id != 'kodi'),
            key=lambda provider: provider.display_name.casefold())

    def select(self):
        self.heading = self.get_localized(32001)
        try:
            providers = self.get_providers()
            if not providers:
                return Dialog().ok(self.heading, self.get_localized(32003))
            selected = Dialog().select(self.heading, [provider.display_name for provider in providers])
            if selected == -1:
                return
            source = providers[selected]
            if not source.is_authorized():
                return Dialog().ok(self.heading, self.get_localized(32004).format(source.display_name))
            self.run(source)
        finally:
            self.addon.openSettings()

    @mutexlock
    def run(self, source):
        importer = HistoryImporter(self.registry.providers['kodi'])
        dialog = DialogProgressSyncBG()
        dialog.heading = self.heading
        dialog.create()
        successful = False
        try:
            dialog.update(0, message=source.display_name)
            items = ImportSource(source, dialog).get_items()
            importer.run(items)
            successful = True
        except (ImportSourceError, KodiLibraryError, DatabaseError, ValueError, TypeError, KeyError) as exc:
            kodi_log(f'Kodi history import from {source.display_name}: {type(exc).__name__}: {exc}', 1)
            Dialog().ok(self.heading, self.get_localized(32005).format(importer.changed))
        finally:
            dialog.close()
            # Refresh even after a partial write failure so completed writes remain visible.
            importer.refresh()
        if successful:
            message = self.get_localized(32006).format(importer.changed)
            if importer.missing_runtime:
                message += '\n' + self.get_localized(32007).format(importer.missing_runtime)
            Dialog().ok(self.heading, message)
