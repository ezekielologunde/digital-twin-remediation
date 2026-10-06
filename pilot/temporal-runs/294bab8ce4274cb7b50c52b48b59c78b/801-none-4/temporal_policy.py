"""Evidence-only shadow decisions, no condition labels or action outcomes."""
KEYS=('timeline_redis','timeline_mongo','post_storage')

def decisions(cached,refresh,last):
    return {name:{'decision':'approve' if all(e[k]['verified'] is True for k in KEYS) else 'abstain'}
            for name,e in [('cached',cached),('refresh_before_wait',refresh),('last_moment_refresh',last)]}
