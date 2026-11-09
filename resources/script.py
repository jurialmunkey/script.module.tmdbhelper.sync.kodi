from xbmc import executebuiltin


def import_history():
    from tmdbhelper_lib.sync.providers.interface import SyncProviderRegistry
    registry = SyncProviderRegistry()
    # Discovery loads provider packages through the core loader, without adding their paths.
    registry.providers
    from tmdbhelper_sync_kodi.settings import ImportHistorySettings
    ImportHistorySettings(registry).select()


def configure_provider():
    executebuiltin(
        'RunScript(plugin.video.themoviedb.helper,configure_sync_provider,'
        'addon_id=script.module.tmdbhelper.sync.kodi)')


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['import_history']:
        import_history()
    else:
        configure_provider()
